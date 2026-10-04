/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2026 TheSuperHackers
**
**	This program is free software: you can redistribute it and/or modify
**	it under the terms of the GNU General Public License as published by
**	the Free Software Foundation, either version 3 of the License, or
**	(at your option) any later version.
**
**	This program is distributed in the hope that it will be useful,
**	but WITHOUT ANY WARRANTY; without even the implied warranty of
**	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

// kernel32 / advapi32 subset implemented on POSIX + Darwin APIs.

#include <windows.h>
#include "win32shim_internal.h"

#include <atomic>
#include <condition_variable>
#include <map>
#include <mutex>
#include <string>
#include <vector>

#include <dirent.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <fnmatch.h>
#include <pwd.h>
#include <sched.h>
#include <signal.h>
#include <sys/mman.h>
#include <sys/param.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
#include <sys/time.h>
#include <time.h>

#include <mach/mach.h>
#include <mach/mach_time.h>
#include <mach-o/dyld.h>
#include <IOKit/pwr_mgt/IOPMLib.h>

//-----------------------------------------------------------------------------
// Handle objects
//-----------------------------------------------------------------------------
namespace
{

enum HandleKind
{
	HK_FILE,
	HK_FIND,
	HK_THREAD,
	HK_EVENT,
	HK_MUTEX,
	HK_SEMAPHORE,
	HK_MAPPING,
};

struct HandleObject
{
	explicit HandleObject(HandleKind k) : kind(k) {}
	virtual ~HandleObject() {}
	HandleKind kind;
};

struct FileHandle : HandleObject
{
	FileHandle() : HandleObject(HK_FILE) {}
	int fd = -1;
	std::string path;
};

struct FindHandle : HandleObject
{
	FindHandle() : HandleObject(HK_FIND) {}
	DIR* dir = nullptr;
	std::string directory;
	std::string pattern;
};

// Waitable objects share one mutex/condvar implementation.
struct WaitableHandle : HandleObject
{
	explicit WaitableHandle(HandleKind k) : HandleObject(k) {}
	std::mutex mutex;
	std::condition_variable cond;
	// For events: signaled state; for semaphores: count; for mutexes: recursion count.
	LONG count = 0;
	LONG maximum = 0;
	bool manualReset = false;
	pthread_t owner {};
	bool finished = false; // threads
};

struct ThreadHandle : WaitableHandle
{
	ThreadHandle() : WaitableHandle(HK_THREAD) {}
	pthread_t thread {};
	LPTHREAD_START_ROUTINE start = nullptr;
	LPVOID param = nullptr;
	DWORD exitCode = STILL_ACTIVE;
	DWORD id = 0;
	bool suspended = false;
};

struct MappingHandle : HandleObject
{
	MappingHandle() : HandleObject(HK_MAPPING) {}
	int fd = -1;
	size_t size = 0;
	DWORD protect = 0;
};

thread_local DWORD t_lastError = 0;

// Created on first use: VirtualAlloc may be called during static initialization.
struct MappedViews
{
	std::mutex mutex;
	std::map<const void*, size_t> views;
};

MappedViews& mappedViews()
{
	static MappedViews* views = new MappedViews();
	return *views;
}

#define g_mappedViewsMutex (mappedViews().mutex)
#define g_mappedViews (mappedViews().views)

DWORD errnoToWin32(int err)
{
	switch (err)
	{
	case 0: return ERROR_SUCCESS;
	case ENOENT: return ERROR_FILE_NOT_FOUND;
	case ENOTDIR: return ERROR_PATH_NOT_FOUND;
	case EACCES:
	case EPERM: return ERROR_ACCESS_DENIED;
	case EEXIST: return ERROR_ALREADY_EXISTS;
	case EBADF: return ERROR_INVALID_HANDLE;
	case ENOMEM: return ERROR_NOT_ENOUGH_MEMORY;
	case EINVAL: return ERROR_INVALID_PARAMETER;
	default: return ERROR_INVALID_PARAMETER;
	}
}

void setErrnoError()
{
	t_lastError = errnoToWin32(errno);
}

template <typename T>
T* handleCast(HANDLE h, HandleKind kind)
{
	if (h == nullptr || h == INVALID_HANDLE_VALUE)
		return nullptr;
	HandleObject* obj = static_cast<HandleObject*>(h);
	if (obj->kind != kind)
		return nullptr;
	return static_cast<T*>(obj);
}

WaitableHandle* waitableCast(HANDLE h)
{
	if (h == nullptr || h == INVALID_HANDLE_VALUE)
		return nullptr;
	HandleObject* obj = static_cast<HandleObject*>(h);
	switch (obj->kind)
	{
	case HK_THREAD:
	case HK_EVENT:
	case HK_MUTEX:
	case HK_SEMAPHORE:
		return static_cast<WaitableHandle*>(obj);
	default:
		return nullptr;
	}
}

// 100ns intervals between 1601-01-01 and 1970-01-01.
const uint64_t kFileTimeEpochOffset = 116444736000000000ULL;

FILETIME timespecToFileTime(const struct timespec& ts)
{
	uint64_t t = (uint64_t)ts.tv_sec * 10000000ULL + (uint64_t)ts.tv_nsec / 100 + kFileTimeEpochOffset;
	FILETIME ft;
	ft.dwLowDateTime = (DWORD)t;
	ft.dwHighDateTime = (DWORD)(t >> 32);
	return ft;
}

uint64_t fileTimeToU64(const FILETIME* ft)
{
	return ((uint64_t)ft->dwHighDateTime << 32) | ft->dwLowDateTime;
}

// Matches a file name against a DOS style wildcard pattern, case insensitively.
// "*.*" matches everything and a trailing '.' means "no extension".
bool matchWildcard(const std::string& pattern, const char* name)
{
	if (pattern == "*" || pattern == "*.*")
		return true;
	if (!pattern.empty() && pattern.back() == '.' && pattern.find('.') == pattern.size() - 1)
	{
		if (strchr(name, '.') != nullptr)
			return false;
		std::string base = pattern.substr(0, pattern.size() - 1);
		return fnmatch(base.c_str(), name, FNM_CASEFOLD) == 0;
	}
	return fnmatch(pattern.c_str(), name, FNM_CASEFOLD) == 0;
}

void fillFindData(const std::string& fullPath, const char* name, LPWIN32_FIND_DATA data)
{
	memset(data, 0, sizeof(*data));
	struct stat st;
	if (stat(fullPath.c_str(), &st) == 0)
	{
		data->dwFileAttributes = S_ISDIR(st.st_mode) ? FILE_ATTRIBUTE_DIRECTORY : FILE_ATTRIBUTE_NORMAL;
		if (!(st.st_mode & S_IWUSR))
			data->dwFileAttributes |= FILE_ATTRIBUTE_READONLY;
		data->ftCreationTime = timespecToFileTime(st.st_birthtimespec);
		data->ftLastAccessTime = timespecToFileTime(st.st_atimespec);
		data->ftLastWriteTime = timespecToFileTime(st.st_mtimespec);
		data->nFileSizeHigh = (DWORD)((uint64_t)st.st_size >> 32);
		data->nFileSizeLow = (DWORD)st.st_size;
	}
	strlcpy(data->cFileName, name, sizeof(data->cFileName));
}

} // namespace

//-----------------------------------------------------------------------------
// Paths
//-----------------------------------------------------------------------------
namespace
{
// Game data paths are written with arbitrary case. On case sensitive volumes,
// find each missing path component case insensitively.
std::string resolvePathCase(const std::string& path)
{
	struct stat st;
	if (path.empty() || stat(path.c_str(), &st) == 0)
		return path;
	std::string result;
	size_t pos = 0;
	if (path[0] == '/')
	{
		result = "/";
		pos = 1;
	}
	while (pos <= path.size())
	{
		size_t next = path.find('/', pos);
		if (next == std::string::npos)
			next = path.size();
		std::string component = path.substr(pos, next - pos);
		pos = next + 1;
		if (component.empty())
			continue;
		std::string dir = result.empty() ? std::string(".") : result;
		std::string candidate = (result.empty() || result == "/") ? result + component : result + "/" + component;
		if (stat(candidate.c_str(), &st) != 0)
		{
			if (DIR* d = opendir(dir.c_str()))
			{
				while (struct dirent* entry = readdir(d))
				{
					if (strcasecmp(entry->d_name, component.c_str()) == 0)
					{
						candidate = (result.empty() || result == "/") ? result + entry->d_name : result + "/" + entry->d_name;
						break;
					}
				}
				closedir(d);
			}
		}
		result = candidate;
	}
	return result;
}
} // namespace

std::string Win32Shim_TranslatePath(const char* path)
{
	if (path == nullptr)
		return std::string();
	std::string out(path);
	for (char& c : out)
	{
		if (c == '\\')
			c = '/';
	}
	// Strip drive letters such as "C:" which have no meaning here.
	if (out.size() >= 2 && isalpha((unsigned char)out[0]) && out[1] == ':')
		out.erase(0, 2);
	return resolvePathCase(out);
}

//-----------------------------------------------------------------------------
// Errors
//-----------------------------------------------------------------------------
DWORD GetLastError()
{
	return t_lastError;
}

void SetLastError(DWORD err)
{
	t_lastError = err;
}

//-----------------------------------------------------------------------------
// Strings
//-----------------------------------------------------------------------------
namespace
{
template <typename IntT, typename CharT>
CharT* integerToString(IntT value, CharT* str, int radix, bool isSigned)
{
	static const char digits[] = "0123456789abcdefghijklmnopqrstuvwxyz";
	CharT* p = str;
	bool negative = false;
	uint64_t v;
	if (isSigned && radix == 10 && (int64_t)value < 0)
	{
		negative = true;
		v = (uint64_t)(-(int64_t)value);
	}
	else
	{
		v = (uint64_t)value;
		if (sizeof(IntT) < sizeof(uint64_t))
			v &= (((uint64_t)1 << (sizeof(IntT) * 8)) - 1);
	}
	CharT buffer[72];
	int len = 0;
	do
	{
		buffer[len++] = (CharT)digits[v % radix];
		v /= radix;
	} while (v != 0);
	if (negative)
		*p++ = '-';
	while (len > 0)
		*p++ = buffer[--len];
	*p = 0;
	return str;
}
} // namespace

char* _itoa(int value, char* str, int radix) { return integerToString(value, str, radix, true); }
char* _ltoa(long value, char* str, int radix) { return integerToString(value, str, radix, true); }
char* _ultoa(unsigned long value, char* str, int radix) { return integerToString(value, str, radix, false); }
char* _i64toa(int64_t value, char* str, int radix) { return integerToString(value, str, radix, true); }
wchar_t* _itow(int value, wchar_t* str, int radix) { return integerToString(value, str, radix, true); }

void _splitpath(const char* path, char* drive, char* dir, char* fname, char* ext)
{
	if (drive)
		*drive = 0;
	if (dir)
		*dir = 0;
	if (fname)
		*fname = 0;
	if (ext)
		*ext = 0;
	if (path == nullptr)
		return;

	if (isalpha((unsigned char)path[0]) && path[1] == ':')
	{
		if (drive)
		{
			drive[0] = path[0];
			drive[1] = ':';
			drive[2] = 0;
		}
		path += 2;
	}

	const char* lastSlash = nullptr;
	for (const char* p = path; *p; ++p)
	{
		if (*p == '/' || *p == '\\')
			lastSlash = p;
	}
	const char* nameStart = lastSlash ? lastSlash + 1 : path;
	if (dir && lastSlash)
	{
		size_t len = (size_t)(nameStart - path);
		memcpy(dir, path, len);
		dir[len] = 0;
	}
	const char* dot = strrchr(nameStart, '.');
	if (dot == nullptr)
		dot = nameStart + strlen(nameStart);
	if (fname)
	{
		size_t len = (size_t)(dot - nameStart);
		memcpy(fname, nameStart, len);
		fname[len] = 0;
	}
	if (ext)
		strcpy(ext, dot);
}

void _makepath(char* path, const char* drive, const char* dir, const char* fname, const char* ext)
{
	*path = 0;
	if (drive && *drive)
	{
		strcat(path, drive);
		if (drive[strlen(drive) - 1] != ':')
			strcat(path, ":");
	}
	if (dir && *dir)
	{
		strcat(path, dir);
		char last = dir[strlen(dir) - 1];
		if (last != '/' && last != '\\')
			strcat(path, "/");
	}
	if (fname)
		strcat(path, fname);
	if (ext && *ext)
	{
		if (*ext != '.')
			strcat(path, ".");
		strcat(path, ext);
	}
}

char* _fullpath(char* absPath, const char* relPath, size_t maxLength)
{
	std::string p = Win32Shim_TranslatePath(relPath);
	char resolved[PATH_MAX];
	if (realpath(p.c_str(), resolved) == nullptr)
	{
		// realpath fails for files that do not exist yet; build the path manually.
		if (p.empty() || p[0] != '/')
		{
			char cwd[PATH_MAX];
			if (getcwd(cwd, sizeof(cwd)) == nullptr)
				return nullptr;
			p = std::string(cwd) + "/" + p;
		}
		strlcpy(resolved, p.c_str(), sizeof(resolved));
	}
	if (absPath == nullptr)
		return strdup(resolved);
	if (strlen(resolved) >= maxLength)
		return nullptr;
	strcpy(absPath, resolved);
	return absPath;
}

// Code pages other than UTF-8 are treated as Latin-1, which matches the
// game's use of CP_ACP for ASCII text.
int MultiByteToWideChar(UINT codePage, DWORD, LPCSTR src, int srcLen, LPWSTR dst, int dstLen)
{
	if (src == nullptr)
		return 0;
	if (srcLen < 0)
		srcLen = (int)strlen(src) + 1;

	std::vector<wchar_t> out;
	out.reserve((size_t)srcLen);
	const unsigned char* s = (const unsigned char*)src;
	const unsigned char* end = s + srcLen;
	while (s < end)
	{
		uint32_t c = *s++;
		if (codePage == CP_UTF8 && c >= 0x80)
		{
			int extra = (c >= 0xF0) ? 3 : (c >= 0xE0) ? 2 : (c >= 0xC0) ? 1 : 0;
			c &= (0x3F >> extra);
			while (extra-- > 0 && s < end)
				c = (c << 6) | (*s++ & 0x3F);
		}
		out.push_back((wchar_t)c);
	}

	if (dstLen == 0)
		return (int)out.size();
	if ((int)out.size() > dstLen)
	{
		t_lastError = ERROR_INSUFFICIENT_BUFFER;
		return 0;
	}
	memcpy(dst, out.data(), out.size() * sizeof(wchar_t));
	return (int)out.size();
}

int WideCharToMultiByte(UINT codePage, DWORD, LPCWSTR src, int srcLen, LPSTR dst, int dstLen, LPCSTR defChar, LPBOOL usedDefChar)
{
	if (src == nullptr)
		return 0;
	if (srcLen < 0)
		srcLen = (int)wcslen(src) + 1;
	if (usedDefChar)
		*usedDefChar = FALSE;

	std::string out;
	out.reserve((size_t)srcLen);
	for (int i = 0; i < srcLen; ++i)
	{
		uint32_t c = (uint32_t)src[i];
		if (codePage == CP_UTF8)
		{
			if (c < 0x80)
				out.push_back((char)c);
			else if (c < 0x800)
			{
				out.push_back((char)(0xC0 | (c >> 6)));
				out.push_back((char)(0x80 | (c & 0x3F)));
			}
			else if (c < 0x10000)
			{
				out.push_back((char)(0xE0 | (c >> 12)));
				out.push_back((char)(0x80 | ((c >> 6) & 0x3F)));
				out.push_back((char)(0x80 | (c & 0x3F)));
			}
			else
			{
				out.push_back((char)(0xF0 | (c >> 18)));
				out.push_back((char)(0x80 | ((c >> 12) & 0x3F)));
				out.push_back((char)(0x80 | ((c >> 6) & 0x3F)));
				out.push_back((char)(0x80 | (c & 0x3F)));
			}
		}
		else if (c < 0x100)
			out.push_back((char)c);
		else
		{
			out.push_back(defChar ? *defChar : '?');
			if (usedDefChar)
				*usedDefChar = TRUE;
		}
	}

	if (dstLen == 0)
		return (int)out.size();
	if ((int)out.size() > dstLen)
	{
		t_lastError = ERROR_INSUFFICIENT_BUFFER;
		return 0;
	}
	memcpy(dst, out.data(), out.size());
	return (int)out.size();
}

//-----------------------------------------------------------------------------
// Memory
//-----------------------------------------------------------------------------
void GlobalMemoryStatus(LPMEMORYSTATUS status)
{
	uint64_t total = 0;
	size_t len = sizeof(total);
	sysctlbyname("hw.memsize", &total, &len, nullptr, 0);

	uint64_t avail = total / 2;
	vm_size_t pageSize = 0;
	host_page_size(mach_host_self(), &pageSize);
	vm_statistics64_data_t vmStats;
	mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
	if (host_statistics64(mach_host_self(), HOST_VM_INFO64, (host_info64_t)&vmStats, &count) == KERN_SUCCESS)
		avail = (uint64_t)(vmStats.free_count + vmStats.inactive_count) * pageSize;

	status->dwLength = sizeof(*status);
	status->dwMemoryLoad = total ? (DWORD)(100 - (avail * 100 / total)) : 0;
	status->dwTotalPhys = (SIZE_T)total;
	status->dwAvailPhys = (SIZE_T)avail;
	status->dwTotalPageFile = (SIZE_T)total;
	status->dwAvailPageFile = (SIZE_T)avail;
	status->dwTotalVirtual = (SIZE_T)total;
	status->dwAvailVirtual = (SIZE_T)avail;
}

LPVOID VirtualAlloc(LPVOID address, SIZE_T size, DWORD type, DWORD protect)
{
	if (address != nullptr && (type & MEM_COMMIT) && !(type & MEM_RESERVE))
	{
		// Committing previously reserved pages.
		mprotect(address, size, PROT_READ | PROT_WRITE);
		return address;
	}
	int prot = (protect == PAGE_NOACCESS) ? PROT_NONE : (protect == PAGE_READONLY) ? PROT_READ : (PROT_READ | PROT_WRITE);
	if (!(type & MEM_COMMIT))
		prot = PROT_NONE;
	void* p = mmap(address, size, prot, MAP_PRIVATE | MAP_ANON, -1, 0);
	if (p == MAP_FAILED)
	{
		setErrnoError();
		return nullptr;
	}
	std::lock_guard<std::mutex> lock(g_mappedViewsMutex);
	g_mappedViews[p] = size;
	return p;
}

BOOL VirtualFree(LPVOID address, SIZE_T size, DWORD type)
{
	if (type & MEM_RELEASE)
	{
		std::lock_guard<std::mutex> lock(g_mappedViewsMutex);
		auto it = g_mappedViews.find(address);
		if (it == g_mappedViews.end())
			return FALSE;
		munmap(address, it->second);
		g_mappedViews.erase(it);
		return TRUE;
	}
	// Decommit
	mprotect(address, size, PROT_NONE);
	madvise(address, size, MADV_FREE);
	return TRUE;
}

BOOL VirtualProtect(LPVOID address, SIZE_T size, DWORD newProtect, PDWORD oldProtect)
{
	if (oldProtect)
		*oldProtect = PAGE_READWRITE;
	int prot = (newProtect == PAGE_NOACCESS) ? PROT_NONE : (newProtect == PAGE_READONLY) ? PROT_READ : (PROT_READ | PROT_WRITE);
	return mprotect(address, size, prot) == 0;
}

//-----------------------------------------------------------------------------
// Time
//-----------------------------------------------------------------------------
namespace
{
uint64_t monotonicNanoseconds()
{
	return clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
}

void tmToSystemTime(const struct tm& t, int ms, LPSYSTEMTIME st)
{
	st->wYear = (WORD)(t.tm_year + 1900);
	st->wMonth = (WORD)(t.tm_mon + 1);
	st->wDayOfWeek = (WORD)t.tm_wday;
	st->wDay = (WORD)t.tm_mday;
	st->wHour = (WORD)t.tm_hour;
	st->wMinute = (WORD)t.tm_min;
	st->wSecond = (WORD)t.tm_sec;
	st->wMilliseconds = (WORD)ms;
}
} // namespace

DWORD GetTickCount()
{
	return (DWORD)(monotonicNanoseconds() / 1000000ULL);
}

ULONGLONG GetTickCount64()
{
	return monotonicNanoseconds() / 1000000ULL;
}

DWORD timeGetTime()
{
	return GetTickCount();
}

BOOL QueryPerformanceCounter(LARGE_INTEGER* count)
{
	count->QuadPart = (LONGLONG)monotonicNanoseconds();
	return TRUE;
}

BOOL QueryPerformanceFrequency(LARGE_INTEGER* freq)
{
	freq->QuadPart = 1000000000LL;
	return TRUE;
}

void GetSystemTime(LPSYSTEMTIME st)
{
	struct timeval tv;
	gettimeofday(&tv, nullptr);
	struct tm t;
	gmtime_r(&tv.tv_sec, &t);
	tmToSystemTime(t, (int)(tv.tv_usec / 1000), st);
}

void GetLocalTime(LPSYSTEMTIME st)
{
	struct timeval tv;
	gettimeofday(&tv, nullptr);
	struct tm t;
	localtime_r(&tv.tv_sec, &t);
	tmToSystemTime(t, (int)(tv.tv_usec / 1000), st);
}

void GetSystemTimeAsFileTime(LPFILETIME ft)
{
	struct timespec ts;
	clock_gettime(CLOCK_REALTIME, &ts);
	*ft = timespecToFileTime(ts);
}

BOOL SystemTimeToFileTime(const SYSTEMTIME* st, LPFILETIME ft)
{
	struct tm t = {};
	t.tm_year = st->wYear - 1900;
	t.tm_mon = st->wMonth - 1;
	t.tm_mday = st->wDay;
	t.tm_hour = st->wHour;
	t.tm_min = st->wMinute;
	t.tm_sec = st->wSecond;
	struct timespec ts;
	ts.tv_sec = timegm(&t);
	ts.tv_nsec = (long)st->wMilliseconds * 1000000L;
	*ft = timespecToFileTime(ts);
	return TRUE;
}

BOOL FileTimeToSystemTime(const FILETIME* ft, LPSYSTEMTIME st)
{
	uint64_t t = fileTimeToU64(ft);
	if (t < kFileTimeEpochOffset)
		return FALSE;
	t -= kFileTimeEpochOffset;
	time_t secs = (time_t)(t / 10000000ULL);
	int ms = (int)((t % 10000000ULL) / 10000ULL);
	struct tm tmv;
	gmtime_r(&secs, &tmv);
	tmToSystemTime(tmv, ms, st);
	return TRUE;
}

BOOL FileTimeToLocalFileTime(const FILETIME* ft, LPFILETIME local)
{
	uint64_t t = fileTimeToU64(ft);
	time_t now = time(nullptr);
	struct tm lt;
	localtime_r(&now, &lt);
	t += (int64_t)lt.tm_gmtoff * 10000000LL;
	local->dwLowDateTime = (DWORD)t;
	local->dwHighDateTime = (DWORD)(t >> 32);
	return TRUE;
}

LONG CompareFileTime(const FILETIME* a, const FILETIME* b)
{
	uint64_t x = fileTimeToU64(a);
	uint64_t y = fileTimeToU64(b);
	return x < y ? -1 : (x > y ? 1 : 0);
}

DWORD GetTimeZoneInformation(LPTIME_ZONE_INFORMATION tz)
{
	memset(tz, 0, sizeof(*tz));
	time_t now = time(nullptr);
	struct tm lt;
	localtime_r(&now, &lt);
	tz->Bias = (LONG)(-lt.tm_gmtoff / 60);
	return lt.tm_isdst > 0 ? TIME_ZONE_ID_DAYLIGHT : TIME_ZONE_ID_STANDARD;
}

int GetDateFormat(LCID, DWORD flags, const SYSTEMTIME* date, LPCSTR, LPSTR out, int outLen)
{
	SYSTEMTIME now;
	if (date == nullptr)
	{
		GetLocalTime(&now);
		date = &now;
	}
	char buffer[64];
	if (flags & DATE_LONGDATE)
	{
		static const char* months[] = { "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December" };
		snprintf(buffer, sizeof(buffer), "%s %d, %d", months[(date->wMonth + 11) % 12], date->wDay, date->wYear);
	}
	else
		snprintf(buffer, sizeof(buffer), "%d/%d/%d", date->wMonth, date->wDay, date->wYear);
	int len = (int)strlen(buffer) + 1;
	if (outLen == 0)
		return len;
	strlcpy(out, buffer, (size_t)outLen);
	return len <= outLen ? len : 0;
}

int GetTimeFormat(LCID, DWORD flags, const SYSTEMTIME* t, LPCSTR, LPSTR out, int outLen)
{
	SYSTEMTIME now;
	if (t == nullptr)
	{
		GetLocalTime(&now);
		t = &now;
	}
	char buffer[64];
	if (flags & TIME_NOSECONDS)
		snprintf(buffer, sizeof(buffer), "%02d:%02d", t->wHour, t->wMinute);
	else
		snprintf(buffer, sizeof(buffer), "%02d:%02d:%02d", t->wHour, t->wMinute, t->wSecond);
	int len = (int)strlen(buffer) + 1;
	if (outLen == 0)
		return len;
	strlcpy(out, buffer, (size_t)outLen);
	return len <= outLen ? len : 0;
}

int GetDateFormatW(LCID locale, DWORD flags, const SYSTEMTIME* date, LPCWSTR, LPWSTR out, int outLen)
{
	char buffer[64];
	int len = GetDateFormat(locale, flags, date, nullptr, buffer, sizeof(buffer));
	if (outLen == 0)
		return len;
	return MultiByteToWideChar(CP_ACP, 0, buffer, -1, out, outLen);
}

int GetTimeFormatW(LCID locale, DWORD flags, const SYSTEMTIME* t, LPCWSTR, LPWSTR out, int outLen)
{
	char buffer[64];
	int len = GetTimeFormat(locale, flags, t, nullptr, buffer, sizeof(buffer));
	if (outLen == 0)
		return len;
	return MultiByteToWideChar(CP_ACP, 0, buffer, -1, out, outLen);
}

//-----------------------------------------------------------------------------
// Critical sections
//-----------------------------------------------------------------------------
void InitializeCriticalSection(LPCRITICAL_SECTION cs)
{
	pthread_mutexattr_t attr;
	pthread_mutexattr_init(&attr);
	pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
	pthread_mutex_init(&cs->mutex, &attr);
	pthread_mutexattr_destroy(&attr);
}

BOOL InitializeCriticalSectionAndSpinCount(LPCRITICAL_SECTION cs, DWORD)
{
	InitializeCriticalSection(cs);
	return TRUE;
}

void DeleteCriticalSection(LPCRITICAL_SECTION cs) { pthread_mutex_destroy(&cs->mutex); }
void EnterCriticalSection(LPCRITICAL_SECTION cs) { pthread_mutex_lock(&cs->mutex); }
BOOL TryEnterCriticalSection(LPCRITICAL_SECTION cs) { return pthread_mutex_trylock(&cs->mutex) == 0; }
void LeaveCriticalSection(LPCRITICAL_SECTION cs) { pthread_mutex_unlock(&cs->mutex); }

//-----------------------------------------------------------------------------
// Threads
//-----------------------------------------------------------------------------
namespace
{
thread_local ThreadHandle* t_currentThread = nullptr;

void* threadTrampoline(void* arg)
{
	ThreadHandle* th = static_cast<ThreadHandle*>(arg);
	t_currentThread = th;
	th->id = GetCurrentThreadId();
	{
		std::unique_lock<std::mutex> lock(th->mutex);
		th->cond.wait(lock, [th] { return !th->suspended; });
	}
	DWORD code = th->start(th->param);
	{
		std::lock_guard<std::mutex> lock(th->mutex);
		th->exitCode = code;
		th->finished = true;
	}
	th->cond.notify_all();
	return nullptr;
}

struct BeginThreadExArgs
{
	unsigned (*start)(void*);
	void* arg;
};

DWORD beginThreadExTrampoline(LPVOID param)
{
	BeginThreadExArgs* args = static_cast<BeginThreadExArgs*>(param);
	BeginThreadExArgs copy = *args;
	delete args;
	return copy.start(copy.arg);
}

struct BeginThreadArgs
{
	void (*start)(void*);
	void* arg;
};

DWORD beginThreadTrampoline(LPVOID param)
{
	BeginThreadArgs* args = static_cast<BeginThreadArgs*>(param);
	BeginThreadArgs copy = *args;
	delete args;
	copy.start(copy.arg);
	return 0;
}
} // namespace

DWORD GetCurrentThreadId()
{
	uint64_t tid = 0;
	pthread_threadid_np(nullptr, &tid);
	return (DWORD)tid;
}

DWORD GetCurrentProcessId()
{
	return (DWORD)getpid();
}

HANDLE GetCurrentThread()
{
	// Pseudo handle, like Windows.
	return (HANDLE)(LONG_PTR)-2;
}

HANDLE GetCurrentProcess()
{
	return (HANDLE)(LONG_PTR)-1;
}

HANDLE CreateThread(LPSECURITY_ATTRIBUTES, SIZE_T stackSize, LPTHREAD_START_ROUTINE start, LPVOID param, DWORD flags, LPDWORD threadId)
{
	ThreadHandle* th = new ThreadHandle();
	th->start = start;
	th->param = param;
	th->suspended = (flags & CREATE_SUSPENDED) != 0;

	pthread_attr_t attr;
	pthread_attr_init(&attr);
	if (stackSize > 0)
		pthread_attr_setstacksize(&attr, (stackSize + 0xFFFF) & ~(SIZE_T)0xFFFF);
	pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
	int rc = pthread_create(&th->thread, &attr, threadTrampoline, th);
	pthread_attr_destroy(&attr);
	if (rc != 0)
	{
		delete th;
		t_lastError = errnoToWin32(rc);
		return nullptr;
	}
	if (threadId)
	{
		uint64_t tid = 0;
		pthread_threadid_np(th->thread, &tid);
		*threadId = (DWORD)tid;
	}
	return th;
}

uintptr_t _beginthreadex(void*, unsigned stackSize, unsigned (*start)(void*), void* arg, unsigned flags, unsigned* threadId)
{
	DWORD id = 0;
	HANDLE h = CreateThread(nullptr, stackSize, beginThreadExTrampoline, new BeginThreadExArgs { start, arg }, flags, &id);
	if (threadId)
		*threadId = id;
	return (uintptr_t)h;
}

uintptr_t _beginthread(void (*start)(void*), unsigned stackSize, void* arg)
{
	HANDLE h = CreateThread(nullptr, stackSize, beginThreadTrampoline, new BeginThreadArgs { start, arg }, 0, nullptr);
	return h ? (uintptr_t)h : (uintptr_t)-1;
}

void ExitThread(DWORD code)
{
	if (ThreadHandle* th = t_currentThread)
	{
		{
			std::lock_guard<std::mutex> lock(th->mutex);
			th->exitCode = code;
			th->finished = true;
		}
		th->cond.notify_all();
	}
	pthread_exit(nullptr);
}

void _endthread() { ExitThread(0); }
void _endthreadex(unsigned retval) { ExitThread(retval); }

BOOL TerminateThread(HANDLE thread, DWORD code)
{
	ThreadHandle* th = handleCast<ThreadHandle>(thread, HK_THREAD);
	if (th == nullptr)
		return FALSE;
	pthread_cancel(th->thread);
	{
		std::lock_guard<std::mutex> lock(th->mutex);
		th->exitCode = code;
		th->finished = true;
	}
	th->cond.notify_all();
	return TRUE;
}

BOOL GetExitCodeThread(HANDLE thread, LPDWORD code)
{
	ThreadHandle* th = handleCast<ThreadHandle>(thread, HK_THREAD);
	if (th == nullptr)
		return FALSE;
	std::lock_guard<std::mutex> lock(th->mutex);
	*code = th->exitCode;
	return TRUE;
}

BOOL SetThreadPriority(HANDLE, int) { return TRUE; }
int GetThreadPriority(HANDLE) { return THREAD_PRIORITY_NORMAL; }
BOOL SetPriorityClass(HANDLE, DWORD) { return TRUE; }
DWORD GetPriorityClass(HANDLE) { return NORMAL_PRIORITY_CLASS; }
DWORD_PTR SetThreadAffinityMask(HANDLE, DWORD_PTR) { return 1; }

DWORD SuspendThread(HANDLE)
{
	// Not supported for running threads on Darwin; only CREATE_SUSPENDED is honored.
	return 0;
}

DWORD ResumeThread(HANDLE thread)
{
	ThreadHandle* th = handleCast<ThreadHandle>(thread, HK_THREAD);
	if (th == nullptr)
		return (DWORD)-1;
	{
		std::lock_guard<std::mutex> lock(th->mutex);
		if (!th->suspended)
			return 0;
		th->suspended = false;
	}
	th->cond.notify_all();
	return 1;
}

void Sleep(DWORD ms)
{
	if (ms == 0)
	{
		sched_yield();
		return;
	}
	struct timespec ts;
	ts.tv_sec = ms / 1000;
	ts.tv_nsec = (long)(ms % 1000) * 1000000L;
	while (nanosleep(&ts, &ts) == -1 && errno == EINTR)
	{
	}
}

DWORD SleepEx(DWORD ms, BOOL)
{
	Sleep(ms);
	return 0;
}

BOOL SwitchToThread()
{
	sched_yield();
	return TRUE;
}

//-----------------------------------------------------------------------------
// Synchronization objects
//-----------------------------------------------------------------------------
namespace
{
struct NamedMutexes
{
	std::mutex lock;
	std::map<std::string, WaitableHandle*> mutexes;
};

NamedMutexes& namedMutexes()
{
	static NamedMutexes* named = new NamedMutexes();
	return *named;
}

#define g_namedMutexesLock (namedMutexes().lock)
#define g_namedMutexes (namedMutexes().mutexes)

// Returns true if the object is signaled and consumes the signal. Caller holds w->mutex.
bool tryAcquire(WaitableHandle* w)
{
	switch (w->kind)
	{
	case HK_THREAD:
		return w->finished;
	case HK_EVENT:
		if (w->count == 0)
			return false;
		if (!w->manualReset)
			w->count = 0;
		return true;
	case HK_SEMAPHORE:
		if (w->count == 0)
			return false;
		--w->count;
		return true;
	case HK_MUTEX:
		if (w->count > 0 && !pthread_equal(w->owner, pthread_self()))
			return false;
		w->owner = pthread_self();
		++w->count;
		return true;
	default:
		return false;
	}
}
} // namespace

HANDLE CreateEvent(LPSECURITY_ATTRIBUTES, BOOL manualReset, BOOL initialState, LPCSTR)
{
	WaitableHandle* w = new WaitableHandle(HK_EVENT);
	w->manualReset = manualReset != FALSE;
	w->count = initialState ? 1 : 0;
	return w;
}

BOOL SetEvent(HANDLE event)
{
	WaitableHandle* w = handleCast<WaitableHandle>(event, HK_EVENT);
	if (w == nullptr)
		return FALSE;
	{
		std::lock_guard<std::mutex> lock(w->mutex);
		w->count = 1;
	}
	w->cond.notify_all();
	return TRUE;
}

BOOL ResetEvent(HANDLE event)
{
	WaitableHandle* w = handleCast<WaitableHandle>(event, HK_EVENT);
	if (w == nullptr)
		return FALSE;
	std::lock_guard<std::mutex> lock(w->mutex);
	w->count = 0;
	return TRUE;
}

BOOL PulseEvent(HANDLE event)
{
	SetEvent(event);
	return ResetEvent(event);
}

HANDLE CreateMutex(LPSECURITY_ATTRIBUTES, BOOL initialOwner, LPCSTR name)
{
	// Named mutexes are only used to detect a second running game instance.
	// Use an exclusive lock file so this works across processes.
	if (name != nullptr && *name)
	{
		std::lock_guard<std::mutex> lock(g_namedMutexesLock);
		auto it = g_namedMutexes.find(name);
		if (it != g_namedMutexes.end())
		{
			t_lastError = ERROR_ALREADY_EXISTS;
			return it->second;
		}
		std::string lockPath = std::string("/tmp/") + name + ".lock";
		for (char& c : lockPath)
		{
			if (c == '\\' || c == ' ')
				c = '_';
		}
		int fd = open(lockPath.c_str(), O_CREAT | O_RDWR, 0644);
		if (fd >= 0 && flock(fd, LOCK_EX | LOCK_NB) != 0)
			t_lastError = ERROR_ALREADY_EXISTS;
		else
			t_lastError = ERROR_SUCCESS;
	}
	else
		t_lastError = ERROR_SUCCESS;

	WaitableHandle* w = new WaitableHandle(HK_MUTEX);
	if (initialOwner)
	{
		w->owner = pthread_self();
		w->count = 1;
	}
	if (name != nullptr && *name)
	{
		std::lock_guard<std::mutex> lock(g_namedMutexesLock);
		g_namedMutexes[name] = w;
	}
	return w;
}

HANDLE OpenMutex(DWORD, BOOL, LPCSTR name)
{
	if (name == nullptr)
		return nullptr;
	std::lock_guard<std::mutex> lock(g_namedMutexesLock);
	auto it = g_namedMutexes.find(name);
	return it != g_namedMutexes.end() ? it->second : nullptr;
}

BOOL ReleaseMutex(HANDLE mutex)
{
	WaitableHandle* w = handleCast<WaitableHandle>(mutex, HK_MUTEX);
	if (w == nullptr)
		return FALSE;
	{
		std::lock_guard<std::mutex> lock(w->mutex);
		if (w->count == 0 || !pthread_equal(w->owner, pthread_self()))
			return FALSE;
		--w->count;
	}
	w->cond.notify_all();
	return TRUE;
}

HANDLE CreateSemaphore(LPSECURITY_ATTRIBUTES, LONG initial, LONG maximum, LPCSTR)
{
	WaitableHandle* w = new WaitableHandle(HK_SEMAPHORE);
	w->count = initial;
	w->maximum = maximum;
	return w;
}

BOOL ReleaseSemaphore(HANDLE sem, LONG count, LPLONG prev)
{
	WaitableHandle* w = handleCast<WaitableHandle>(sem, HK_SEMAPHORE);
	if (w == nullptr)
		return FALSE;
	{
		std::lock_guard<std::mutex> lock(w->mutex);
		if (prev)
			*prev = w->count;
		if (w->count + count > w->maximum)
			return FALSE;
		w->count += count;
	}
	w->cond.notify_all();
	return TRUE;
}

DWORD WaitForSingleObject(HANDLE handle, DWORD ms)
{
	WaitableHandle* w = waitableCast(handle);
	if (w == nullptr)
		return WAIT_FAILED;
	std::unique_lock<std::mutex> lock(w->mutex);
	if (ms == INFINITE)
	{
		w->cond.wait(lock, [w] { return tryAcquire(w); });
		return WAIT_OBJECT_0;
	}
	if (w->cond.wait_for(lock, std::chrono::milliseconds(ms), [w] { return tryAcquire(w); }))
		return WAIT_OBJECT_0;
	return WAIT_TIMEOUT;
}

DWORD WaitForMultipleObjects(DWORD count, const HANDLE* handles, BOOL waitAll, DWORD ms)
{
	// Simple polling implementation; only used in non-critical paths.
	uint64_t deadline = (ms == INFINITE) ? UINT64_MAX : GetTickCount64() + ms;
	for (;;)
	{
		DWORD signaled = 0;
		for (DWORD i = 0; i < count; ++i)
		{
			if (WaitForSingleObject(handles[i], 0) == WAIT_OBJECT_0)
			{
				if (!waitAll)
					return WAIT_OBJECT_0 + i;
				++signaled;
			}
		}
		if (waitAll && signaled == count)
			return WAIT_OBJECT_0;
		if (GetTickCount64() >= deadline)
			return WAIT_TIMEOUT;
		Sleep(1);
	}
}

BOOL CloseHandle(HANDLE handle)
{
	if (handle == nullptr || handle == INVALID_HANDLE_VALUE || handle == GetCurrentThread())
		return FALSE;
	HandleObject* obj = static_cast<HandleObject*>(handle);
	switch (obj->kind)
	{
	case HK_FILE:
	{
		FileHandle* f = static_cast<FileHandle*>(obj);
		if (f->fd >= 0)
			close(f->fd);
		break;
	}
	case HK_MAPPING:
	{
		MappingHandle* m = static_cast<MappingHandle*>(obj);
		if (m->fd >= 0)
			close(m->fd);
		break;
	}
	case HK_THREAD:
		// Threads are detached; leak the handle object if still running since
		// the trampoline references it.
		if (!static_cast<ThreadHandle*>(obj)->finished)
			return TRUE;
		break;
	case HK_MUTEX:
	{
		// Named mutexes stay registered for the process lifetime.
		std::lock_guard<std::mutex> lock(g_namedMutexesLock);
		for (auto& kv : g_namedMutexes)
		{
			if (kv.second == obj)
				return TRUE;
		}
		break;
	}
	default:
		break;
	}
	delete obj;
	return TRUE;
}

//-----------------------------------------------------------------------------
// Interlocked
//-----------------------------------------------------------------------------
LONG InterlockedIncrement(LONG volatile* value) { return __atomic_add_fetch(value, 1, __ATOMIC_SEQ_CST); }
LONG InterlockedDecrement(LONG volatile* value) { return __atomic_sub_fetch(value, 1, __ATOMIC_SEQ_CST); }
LONG InterlockedExchange(LONG volatile* target, LONG value) { return __atomic_exchange_n(target, value, __ATOMIC_SEQ_CST); }
LONG InterlockedExchangeAdd(LONG volatile* target, LONG value) { return __atomic_fetch_add(target, value, __ATOMIC_SEQ_CST); }

LONG InterlockedCompareExchange(LONG volatile* dest, LONG exchange, LONG comparand)
{
	__atomic_compare_exchange_n(dest, &comparand, exchange, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
	return comparand;
}

PVOID InterlockedExchangePointer(PVOID volatile* target, PVOID value)
{
	return __atomic_exchange_n(target, value, __ATOMIC_SEQ_CST);
}

PVOID InterlockedCompareExchangePointer(PVOID volatile* dest, PVOID exchange, PVOID comparand)
{
	__atomic_compare_exchange_n(dest, &comparand, exchange, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
	return comparand;
}

//-----------------------------------------------------------------------------
// TLS
//-----------------------------------------------------------------------------
DWORD TlsAlloc()
{
	pthread_key_t key;
	if (pthread_key_create(&key, nullptr) != 0)
		return TLS_OUT_OF_INDEXES;
	return (DWORD)key;
}

BOOL TlsFree(DWORD index) { return pthread_key_delete((pthread_key_t)index) == 0; }
LPVOID TlsGetValue(DWORD index) { return pthread_getspecific((pthread_key_t)index); }
BOOL TlsSetValue(DWORD index, LPVOID value) { return pthread_setspecific((pthread_key_t)index, value) == 0; }

//-----------------------------------------------------------------------------
// Files
//-----------------------------------------------------------------------------
HANDLE CreateFile(LPCSTR name, DWORD access, DWORD, LPSECURITY_ATTRIBUTES, DWORD disposition, DWORD, HANDLE)
{
	std::string path = Win32Shim_TranslatePath(name);
	int flags = 0;
	if ((access & GENERIC_READ) && (access & GENERIC_WRITE))
		flags = O_RDWR;
	else if (access & GENERIC_WRITE)
		flags = O_WRONLY;
	else
		flags = O_RDONLY;

	switch (disposition)
	{
	case CREATE_NEW: flags |= O_CREAT | O_EXCL; break;
	case CREATE_ALWAYS: flags |= O_CREAT | O_TRUNC; break;
	case OPEN_EXISTING: break;
	case OPEN_ALWAYS: flags |= O_CREAT; break;
	case TRUNCATE_EXISTING: flags |= O_TRUNC; break;
	}

	int fd = open(path.c_str(), flags, 0644);
	if (fd < 0)
	{
		setErrnoError();
		return INVALID_HANDLE_VALUE;
	}
	struct stat st;
	if (fstat(fd, &st) == 0 && S_ISDIR(st.st_mode))
	{
		close(fd);
		t_lastError = ERROR_ACCESS_DENIED;
		return INVALID_HANDLE_VALUE;
	}
	FileHandle* f = new FileHandle();
	f->fd = fd;
	f->path = path;
	t_lastError = ERROR_SUCCESS;
	return f;
}

BOOL ReadFile(HANDLE file, LPVOID buffer, DWORD toRead, LPDWORD readOut, LPOVERLAPPED)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	if (f == nullptr)
	{
		t_lastError = ERROR_INVALID_HANDLE;
		return FALSE;
	}
	DWORD total = 0;
	while (total < toRead)
	{
		ssize_t n = read(f->fd, (char*)buffer + total, toRead - total);
		if (n < 0)
		{
			if (errno == EINTR)
				continue;
			setErrnoError();
			if (readOut)
				*readOut = total;
			return FALSE;
		}
		if (n == 0)
			break;
		total += (DWORD)n;
	}
	if (readOut)
		*readOut = total;
	return TRUE;
}

BOOL WriteFile(HANDLE file, LPCVOID buffer, DWORD toWrite, LPDWORD writtenOut, LPOVERLAPPED)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	if (f == nullptr)
	{
		t_lastError = ERROR_INVALID_HANDLE;
		return FALSE;
	}
	DWORD total = 0;
	while (total < toWrite)
	{
		ssize_t n = write(f->fd, (const char*)buffer + total, toWrite - total);
		if (n < 0)
		{
			if (errno == EINTR)
				continue;
			setErrnoError();
			if (writtenOut)
				*writtenOut = total;
			return FALSE;
		}
		total += (DWORD)n;
	}
	if (writtenOut)
		*writtenOut = total;
	return TRUE;
}

DWORD SetFilePointer(HANDLE file, LONG distance, PLONG distanceHigh, DWORD method)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	if (f == nullptr)
	{
		t_lastError = ERROR_INVALID_HANDLE;
		return INVALID_SET_FILE_POINTER;
	}
	off_t offset = distanceHigh ? (off_t)(((int64_t)*distanceHigh << 32) | (uint32_t)distance) : (off_t)distance;
	int whence = (method == FILE_BEGIN) ? SEEK_SET : (method == FILE_CURRENT) ? SEEK_CUR : SEEK_END;
	off_t result = lseek(f->fd, offset, whence);
	if (result < 0)
	{
		setErrnoError();
		return INVALID_SET_FILE_POINTER;
	}
	if (distanceHigh)
		*distanceHigh = (LONG)((uint64_t)result >> 32);
	return (DWORD)result;
}

BOOL SetEndOfFile(HANDLE file)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	if (f == nullptr)
		return FALSE;
	off_t pos = lseek(f->fd, 0, SEEK_CUR);
	return ftruncate(f->fd, pos) == 0;
}

BOOL FlushFileBuffers(HANDLE file)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	return f != nullptr && fsync(f->fd) == 0;
}

DWORD GetFileSize(HANDLE file, LPDWORD high)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	struct stat st;
	if (f == nullptr || fstat(f->fd, &st) != 0)
		return INVALID_FILE_SIZE;
	if (high)
		*high = (DWORD)((uint64_t)st.st_size >> 32);
	return (DWORD)st.st_size;
}

BOOL GetFileTime(HANDLE file, LPFILETIME creation, LPFILETIME access, LPFILETIME writeTime)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	struct stat st;
	if (f == nullptr || fstat(f->fd, &st) != 0)
		return FALSE;
	if (creation)
		*creation = timespecToFileTime(st.st_birthtimespec);
	if (access)
		*access = timespecToFileTime(st.st_atimespec);
	if (writeTime)
		*writeTime = timespecToFileTime(st.st_mtimespec);
	return TRUE;
}

BOOL SetFileTime(HANDLE file, const FILETIME*, const FILETIME* access, const FILETIME* writeTime)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	if (f == nullptr)
		return FALSE;
	struct timespec times[2];
	times[0].tv_nsec = UTIME_OMIT;
	times[1].tv_nsec = UTIME_OMIT;
	auto toTs = [](const FILETIME* ft, struct timespec& ts) {
		uint64_t t = fileTimeToU64(ft) - kFileTimeEpochOffset;
		ts.tv_sec = (time_t)(t / 10000000ULL);
		ts.tv_nsec = (long)((t % 10000000ULL) * 100);
	};
	if (access)
		toTs(access, times[0]);
	if (writeTime)
		toTs(writeTime, times[1]);
	return futimens(f->fd, times) == 0;
}

BOOL GetFileInformationByHandle(HANDLE file, LPBY_HANDLE_FILE_INFORMATION info)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	struct stat st;
	if (f == nullptr || fstat(f->fd, &st) != 0)
		return FALSE;
	memset(info, 0, sizeof(*info));
	info->dwFileAttributes = S_ISDIR(st.st_mode) ? FILE_ATTRIBUTE_DIRECTORY : FILE_ATTRIBUTE_NORMAL;
	info->ftCreationTime = timespecToFileTime(st.st_birthtimespec);
	info->ftLastAccessTime = timespecToFileTime(st.st_atimespec);
	info->ftLastWriteTime = timespecToFileTime(st.st_mtimespec);
	info->dwVolumeSerialNumber = (DWORD)st.st_dev;
	info->nFileSizeHigh = (DWORD)((uint64_t)st.st_size >> 32);
	info->nFileSizeLow = (DWORD)st.st_size;
	info->nNumberOfLinks = (DWORD)st.st_nlink;
	info->nFileIndexHigh = (DWORD)((uint64_t)st.st_ino >> 32);
	info->nFileIndexLow = (DWORD)st.st_ino;
	return TRUE;
}

DWORD GetFileAttributes(LPCSTR name)
{
	std::string path = Win32Shim_TranslatePath(name);
	struct stat st;
	if (stat(path.c_str(), &st) != 0)
	{
		setErrnoError();
		return INVALID_FILE_ATTRIBUTES;
	}
	DWORD attrs = S_ISDIR(st.st_mode) ? FILE_ATTRIBUTE_DIRECTORY : FILE_ATTRIBUTE_NORMAL;
	if (!(st.st_mode & S_IWUSR))
		attrs |= FILE_ATTRIBUTE_READONLY;
	return attrs;
}

BOOL SetFileAttributes(LPCSTR name, DWORD attrs)
{
	std::string path = Win32Shim_TranslatePath(name);
	struct stat st;
	if (stat(path.c_str(), &st) != 0)
		return FALSE;
	mode_t mode = st.st_mode;
	if (attrs & FILE_ATTRIBUTE_READONLY)
		mode &= ~(S_IWUSR | S_IWGRP | S_IWOTH);
	else
		mode |= S_IWUSR;
	return chmod(path.c_str(), mode) == 0;
}

BOOL DeleteFile(LPCSTR name)
{
	std::string path = Win32Shim_TranslatePath(name);
	if (unlink(path.c_str()) != 0)
	{
		setErrnoError();
		return FALSE;
	}
	return TRUE;
}

BOOL CopyFile(LPCSTR from, LPCSTR to, BOOL failIfExists)
{
	std::string src = Win32Shim_TranslatePath(from);
	std::string dst = Win32Shim_TranslatePath(to);
	int in = open(src.c_str(), O_RDONLY);
	if (in < 0)
	{
		setErrnoError();
		return FALSE;
	}
	int out = open(dst.c_str(), O_WRONLY | O_CREAT | (failIfExists ? O_EXCL : O_TRUNC), 0644);
	if (out < 0)
	{
		setErrnoError();
		close(in);
		return FALSE;
	}
	char buffer[65536];
	ssize_t n;
	bool ok = true;
	while ((n = read(in, buffer, sizeof(buffer))) > 0)
	{
		if (write(out, buffer, (size_t)n) != n)
		{
			ok = false;
			break;
		}
	}
	close(in);
	close(out);
	return ok && n >= 0;
}

BOOL MoveFile(LPCSTR from, LPCSTR to)
{
	std::string src = Win32Shim_TranslatePath(from);
	std::string dst = Win32Shim_TranslatePath(to);
	if (access(dst.c_str(), F_OK) == 0)
	{
		t_lastError = ERROR_ALREADY_EXISTS;
		return FALSE;
	}
	return rename(src.c_str(), dst.c_str()) == 0;
}

BOOL MoveFileEx(LPCSTR from, LPCSTR to, DWORD flags)
{
	if (to == nullptr)
		return DeleteFile(from);
	if (!(flags & MOVEFILE_REPLACE_EXISTING))
		return MoveFile(from, to);
	std::string src = Win32Shim_TranslatePath(from);
	std::string dst = Win32Shim_TranslatePath(to);
	return rename(src.c_str(), dst.c_str()) == 0;
}

BOOL CreateDirectory(LPCSTR name, LPSECURITY_ATTRIBUTES)
{
	std::string path = Win32Shim_TranslatePath(name);
	if (mkdir(path.c_str(), 0755) != 0)
	{
		setErrnoError();
		return FALSE;
	}
	return TRUE;
}

BOOL RemoveDirectory(LPCSTR name)
{
	std::string path = Win32Shim_TranslatePath(name);
	return rmdir(path.c_str()) == 0;
}

DWORD GetCurrentDirectory(DWORD len, LPSTR buffer)
{
	char cwd[PATH_MAX];
	if (getcwd(cwd, sizeof(cwd)) == nullptr)
		return 0;
	DWORD needed = (DWORD)strlen(cwd);
	if (buffer == nullptr || len <= needed)
		return needed + 1;
	strcpy(buffer, cwd);
	return needed;
}

BOOL SetCurrentDirectory(LPCSTR name)
{
	std::string path = Win32Shim_TranslatePath(name);
	return chdir(path.c_str()) == 0;
}

DWORD GetModuleFileName(HMODULE, LPSTR buffer, DWORD len)
{
	char path[PATH_MAX];
	uint32_t size = sizeof(path);
	if (_NSGetExecutablePath(path, &size) != 0)
		return 0;
	char resolved[PATH_MAX];
	if (realpath(path, resolved) == nullptr)
		strlcpy(resolved, path, sizeof(resolved));
	strlcpy(buffer, resolved, len);
	return (DWORD)strlen(buffer);
}

HMODULE GetModuleHandle(LPCSTR)
{
	// Any non-null value; only used as an opaque instance handle.
	return (HMODULE)(uintptr_t)0x400000;
}

HMODULE LoadLibrary(LPCSTR name)
{
	// Windows DLLs cannot be loaded here.
	(void)name;
	t_lastError = ERROR_FILE_NOT_FOUND;
	return nullptr;
}

BOOL FreeLibrary(HMODULE module)
{
	return module != nullptr;
}

FARPROC GetProcAddress(HMODULE, LPCSTR)
{
	return nullptr;
}

DWORD GetTempPath(DWORD len, LPSTR buffer)
{
	const char* tmp = getenv("TMPDIR");
	std::string path = tmp ? tmp : "/tmp/";
	if (path.back() != '/')
		path += '/';
	strlcpy(buffer, path.c_str(), len);
	return (DWORD)path.size();
}

UINT GetTempFileName(LPCSTR path, LPCSTR prefix, UINT unique, LPSTR out)
{
	std::string dir = Win32Shim_TranslatePath(path);
	if (!dir.empty() && dir.back() != '/')
		dir += '/';
	if (unique == 0)
		unique = (UINT)(GetTickCount() & 0xFFFF);
	snprintf(out, MAX_PATH, "%s%.3s%04X.tmp", dir.c_str(), prefix ? prefix : "", unique);
	return unique;
}

DWORD GetFullPathName(LPCSTR name, DWORD len, LPSTR buffer, LPSTR* filePart)
{
	char full[PATH_MAX];
	if (_fullpath(full, name, sizeof(full)) == nullptr)
		return 0;
	DWORD needed = (DWORD)strlen(full);
	if (len <= needed)
		return needed + 1;
	strcpy(buffer, full);
	if (filePart)
	{
		char* slash = strrchr(buffer, '/');
		*filePart = slash ? slash + 1 : buffer;
	}
	return needed;
}

UINT GetWindowsDirectory(LPSTR buffer, UINT len)
{
	strlcpy(buffer, "/", len);
	return 1;
}

UINT GetSystemDirectory(LPSTR buffer, UINT len)
{
	strlcpy(buffer, "/", len);
	return 1;
}

UINT GetDriveType(LPCSTR) { return DRIVE_FIXED; }
DWORD GetLogicalDrives() { return 1u << 2; } // "C:"

BOOL GetVolumeInformation(LPCSTR, LPSTR volName, DWORD volNameLen, LPDWORD serial, LPDWORD maxComponent, LPDWORD fsFlags, LPSTR fsName, DWORD fsNameLen)
{
	if (volName && volNameLen)
		strlcpy(volName, "Macintosh HD", volNameLen);
	if (serial)
		*serial = 0x12345678;
	if (maxComponent)
		*maxComponent = 255;
	if (fsFlags)
		*fsFlags = 0;
	if (fsName && fsNameLen)
		strlcpy(fsName, "APFS", fsNameLen);
	return TRUE;
}

BOOL GetDiskFreeSpaceEx(LPCSTR dir, PULARGE_INTEGER freeToCaller, PULARGE_INTEGER total, PULARGE_INTEGER totalFree)
{
	std::string path = dir ? Win32Shim_TranslatePath(dir) : std::string(".");
	if (path.empty())
		path = ".";
	struct statfs st;
	if (statfs(path.c_str(), &st) != 0)
		return FALSE;
	if (freeToCaller)
		freeToCaller->QuadPart = (ULONGLONG)st.f_bavail * st.f_bsize;
	if (total)
		total->QuadPart = (ULONGLONG)st.f_blocks * st.f_bsize;
	if (totalFree)
		totalFree->QuadPart = (ULONGLONG)st.f_bfree * st.f_bsize;
	return TRUE;
}

BOOL GetDiskFreeSpace(LPCSTR root, LPDWORD sectorsPerCluster, LPDWORD bytesPerSector, LPDWORD freeClusters, LPDWORD totalClusters)
{
	ULARGE_INTEGER freeBytes, totalBytes;
	if (!GetDiskFreeSpaceEx(root, &freeBytes, &totalBytes, nullptr))
		return FALSE;
	const DWORD clusterSize = 4096;
	if (sectorsPerCluster)
		*sectorsPerCluster = 8;
	if (bytesPerSector)
		*bytesPerSector = 512;
	if (freeClusters)
		*freeClusters = (DWORD)std::min<ULONGLONG>(freeBytes.QuadPart / clusterSize, 0xFFFFFFFF);
	if (totalClusters)
		*totalClusters = (DWORD)std::min<ULONGLONG>(totalBytes.QuadPart / clusterSize, 0xFFFFFFFF);
	return TRUE;
}

HANDLE FindFirstFile(LPCSTR pattern, LPWIN32_FIND_DATA data)
{
	std::string path = Win32Shim_TranslatePath(pattern);
	std::string directory;
	std::string mask;
	size_t slash = path.rfind('/');
	if (slash == std::string::npos)
	{
		directory = ".";
		mask = path;
	}
	else
	{
		directory = path.substr(0, slash);
		if (directory.empty())
			directory = "/";
		mask = path.substr(slash + 1);
	}

	DIR* dir = opendir(directory.c_str());
	if (dir == nullptr)
	{
		setErrnoError();
		return INVALID_HANDLE_VALUE;
	}
	FindHandle* f = new FindHandle();
	f->dir = dir;
	f->directory = directory;
	f->pattern = mask;
	if (!FindNextFile(f, data))
	{
		closedir(dir);
		f->dir = nullptr;
		delete f;
		t_lastError = ERROR_FILE_NOT_FOUND;
		return INVALID_HANDLE_VALUE;
	}
	return f;
}

BOOL FindNextFile(HANDLE find, LPWIN32_FIND_DATA data)
{
	FindHandle* f = handleCast<FindHandle>(find, HK_FIND);
	if (f == nullptr || f->dir == nullptr)
		return FALSE;
	while (struct dirent* entry = readdir(f->dir))
	{
		if (matchWildcard(f->pattern, entry->d_name))
		{
			fillFindData(f->directory + "/" + entry->d_name, entry->d_name, data);
			return TRUE;
		}
	}
	t_lastError = ERROR_NO_MORE_FILES;
	return FALSE;
}

BOOL FindClose(HANDLE find)
{
	FindHandle* f = handleCast<FindHandle>(find, HK_FIND);
	if (f == nullptr)
		return FALSE;
	if (f->dir)
		closedir(f->dir);
	delete f;
	return TRUE;
}

HANDLE CreateFileMapping(HANDLE file, LPSECURITY_ATTRIBUTES, DWORD protect, DWORD sizeHigh, DWORD sizeLow, LPCSTR)
{
	FileHandle* f = handleCast<FileHandle>(file, HK_FILE);
	if (f == nullptr)
		return nullptr;
	MappingHandle* m = new MappingHandle();
	m->fd = dup(f->fd);
	m->protect = protect;
	m->size = ((size_t)sizeHigh << 32) | sizeLow;
	if (m->size == 0)
	{
		struct stat st;
		fstat(m->fd, &st);
		m->size = (size_t)st.st_size;
	}
	return m;
}

LPVOID MapViewOfFile(HANDLE mapping, DWORD access, DWORD offsetHigh, DWORD offsetLow, SIZE_T bytes)
{
	MappingHandle* m = handleCast<MappingHandle>(mapping, HK_MAPPING);
	if (m == nullptr)
		return nullptr;
	off_t offset = (off_t)(((uint64_t)offsetHigh << 32) | offsetLow);
	size_t size = bytes ? bytes : m->size - (size_t)offset;
	int prot = (access & FILE_MAP_WRITE) ? (PROT_READ | PROT_WRITE) : PROT_READ;
	int flags = (access & FILE_MAP_COPY) ? MAP_PRIVATE : MAP_SHARED;
	void* p = mmap(nullptr, size, prot, flags, m->fd, offset);
	if (p == MAP_FAILED)
		return nullptr;
	std::lock_guard<std::mutex> lock(g_mappedViewsMutex);
	g_mappedViews[p] = size;
	return p;
}

BOOL UnmapViewOfFile(LPCVOID address)
{
	std::lock_guard<std::mutex> lock(g_mappedViewsMutex);
	auto it = g_mappedViews.find(address);
	if (it == g_mappedViews.end())
		return FALSE;
	munmap(const_cast<void*>(address), it->second);
	g_mappedViews.erase(it);
	return TRUE;
}

//-----------------------------------------------------------------------------
// Process / system
//-----------------------------------------------------------------------------
extern int __argc;
extern char** __argv;

namespace
{
std::string& commandLine()
{
	static std::string* line = new std::string();
	return *line;
}
#define g_commandLine (commandLine())
} // namespace

void Win32Shim_SetCommandLine(int argc, char** argv)
{
	__argc = argc;
	__argv = argv;
	g_commandLine.clear();
	for (int i = 0; i < argc; ++i)
	{
		if (i > 0)
			g_commandLine += ' ';
		bool quote = strchr(argv[i], ' ') != nullptr;
		if (quote)
			g_commandLine += '"';
		g_commandLine += argv[i];
		if (quote)
			g_commandLine += '"';
	}
}

LPSTR GetCommandLine()
{
	return const_cast<LPSTR>(g_commandLine.c_str());
}

void GetSystemInfo(LPSYSTEM_INFO info)
{
	memset(info, 0, sizeof(*info));
	info->dwPageSize = (DWORD)getpagesize();
	info->dwAllocationGranularity = 65536;
	int ncpu = 1;
	size_t len = sizeof(ncpu);
	sysctlbyname("hw.logicalcpu", &ncpu, &len, nullptr, 0);
	info->dwNumberOfProcessors = (DWORD)ncpu;
	info->dwActiveProcessorMask = (ncpu >= 64) ? ~(DWORD_PTR)0 : (((DWORD_PTR)1 << ncpu) - 1);
	info->wProcessorArchitecture = 12; // PROCESSOR_ARCHITECTURE_ARM64
	info->lpMinimumApplicationAddress = (LPVOID)0x10000;
	info->lpMaximumApplicationAddress = (LPVOID)0x7FFFFFFFFFFF;
}

BOOL GetVersionEx(LPOSVERSIONINFO info)
{
	// Report Windows 10 so version checks take modern code paths.
	info->dwMajorVersion = 10;
	info->dwMinorVersion = 0;
	info->dwBuildNumber = 19041;
	info->dwPlatformId = VER_PLATFORM_WIN32_NT;
	info->szCSDVersion[0] = 0;
	return TRUE;
}

DWORD GetVersion()
{
	return 10 | (0 << 8) | (19041u << 16);
}

BOOL GetComputerName(LPSTR buffer, LPDWORD len)
{
	char name[256];
	if (gethostname(name, sizeof(name)) != 0)
		strcpy(name, "Mac");
	char* dot = strchr(name, '.');
	if (dot)
		*dot = 0;
	if (strlen(name) >= *len)
	{
		*len = (DWORD)strlen(name) + 1;
		t_lastError = ERROR_INSUFFICIENT_BUFFER;
		return FALSE;
	}
	strcpy(buffer, name);
	*len = (DWORD)strlen(name);
	return TRUE;
}

BOOL GetUserName(LPSTR buffer, LPDWORD len)
{
	const char* name = getenv("USER");
	if (name == nullptr)
	{
		struct passwd* pw = getpwuid(getuid());
		name = pw ? pw->pw_name : "Player";
	}
	if (strlen(name) >= *len)
	{
		*len = (DWORD)strlen(name) + 1;
		t_lastError = ERROR_INSUFFICIENT_BUFFER;
		return FALSE;
	}
	strcpy(buffer, name);
	*len = (DWORD)strlen(name) + 1;
	return TRUE;
}

DWORD GetEnvironmentVariable(LPCSTR name, LPSTR buffer, DWORD len)
{
	const char* value = getenv(name);
	if (value == nullptr)
	{
		t_lastError = 203; // ERROR_ENVVAR_NOT_FOUND
		return 0;
	}
	DWORD needed = (DWORD)strlen(value);
	if (buffer == nullptr || len <= needed)
		return needed + 1;
	strcpy(buffer, value);
	return needed;
}

BOOL SetEnvironmentVariable(LPCSTR name, LPCSTR value)
{
	if (value == nullptr)
		return unsetenv(name) == 0;
	return setenv(name, value, 1) == 0;
}

void ExitProcess(UINT code)
{
	exit((int)code);
}

BOOL TerminateProcess(HANDLE process, UINT code)
{
	if (process == GetCurrentProcess())
		_exit((int)code);
	return FALSE;
}

void OutputDebugStringA(LPCSTR str)
{
	if (str)
		fputs(str, stderr);
}

void OutputDebugStringW(LPCWSTR str)
{
	if (str)
		fprintf(stderr, "%ls", str);
}

BOOL IsDebuggerPresent()
{
	int mib[4] = { CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid() };
	struct kinfo_proc info;
	memset(&info, 0, sizeof(info));
	size_t size = sizeof(info);
	if (sysctl(mib, 4, &info, &size, nullptr, 0) != 0)
		return FALSE;
	return (info.kp_proc.p_flag & P_TRACED) != 0;
}

void DebugBreak()
{
	__builtin_debugtrap();
}

LANGID GetUserDefaultLangID() { return MAKELANGID(LANG_ENGLISH, SUBLANG_ENGLISH_US); }
LANGID GetSystemDefaultLangID() { return MAKELANGID(LANG_ENGLISH, SUBLANG_ENGLISH_US); }
LCID GetUserDefaultLCID() { return MAKELANGID(LANG_ENGLISH, SUBLANG_ENGLISH_US); }

BOOL CreateProcess(LPCSTR, LPSTR, LPSECURITY_ATTRIBUTES, LPSECURITY_ATTRIBUTES, BOOL, DWORD, LPVOID, LPCSTR, LPSTARTUPINFO, LPPROCESS_INFORMATION)
{
	// Launching Windows executables (patchers, browsers) is not supported.
	t_lastError = ERROR_FILE_NOT_FOUND;
	return FALSE;
}

BOOL GetExitCodeProcess(HANDLE, LPDWORD code)
{
	if (code)
		*code = 0;
	return FALSE;
}

void GetStartupInfo(LPSTARTUPINFO si)
{
	memset(si, 0, sizeof(*si));
	si->cb = sizeof(*si);
}

int MulDiv(int number, int numerator, int denominator)
{
	if (denominator == 0)
		return -1;
	return (int)(((int64_t)number * numerator) / denominator);
}

DWORD FormatMessage(DWORD flags, LPCVOID, DWORD messageId, DWORD, LPSTR buffer, DWORD size, va_list*)
{
	char text[256];
	snprintf(text, sizeof(text), "Error %u", (unsigned)messageId);
	if (flags & FORMAT_MESSAGE_ALLOCATE_BUFFER)
	{
		*(LPSTR*)buffer = (LPSTR)LocalAlloc(LPTR, strlen(text) + 1);
		strcpy(*(LPSTR*)buffer, text);
		return (DWORD)strlen(text);
	}
	strlcpy(buffer, text, size);
	return (DWORD)strlen(buffer);
}
char* _ui64toa(uint64_t value, char* str, int radix) { return integerToString(value, str, radix, false); }

EXECUTION_STATE SetThreadExecutionState(EXECUTION_STATE flags)
{
	// Keep the display awake while the game asks for it, using an IOKit power assertion.
	static IOPMAssertionID assertion = kIOPMNullAssertionID;
	if ((flags & ES_DISPLAY_REQUIRED) && assertion == kIOPMNullAssertionID)
		IOPMAssertionCreateWithName(kIOPMAssertionTypeNoDisplaySleep, kIOPMAssertionLevelOn, CFSTR("Command & Conquer Generals"), &assertion);
	else if (!(flags & ES_DISPLAY_REQUIRED) && assertion != kIOPMNullAssertionID)
	{
		IOPMAssertionRelease(assertion);
		assertion = kIOPMNullAssertionID;
	}
	return ES_CONTINUOUS;
}

// Weak so the identical GameSpy definitions take precedence when linked.
extern "C" __attribute__((weak)) char* _strlwr(char* s)
{
	for (char* p = s; *p; ++p)
		*p = (char)tolower((unsigned char)*p);
	return s;
}

extern "C" __attribute__((weak)) char* _strupr(char* s)
{
	for (char* p = s; *p; ++p)
		*p = (char)toupper((unsigned char)*p);
	return s;
}

DWORD FormatMessageW(DWORD flags, LPCVOID, DWORD messageId, DWORD, LPWSTR buffer, DWORD size, va_list*)
{
	wchar_t text[256];
	swprintf(text, 256, L"Error %u", (unsigned)messageId);
	if (flags & FORMAT_MESSAGE_ALLOCATE_BUFFER)
	{
		*(LPWSTR*)buffer = (LPWSTR)LocalAlloc(LPTR, (wcslen(text) + 1) * sizeof(wchar_t));
		wcscpy(*(LPWSTR*)buffer, text);
		return (DWORD)wcslen(text);
	}
	wcsncpy(buffer, text, size);
	if (size)
		buffer[size - 1] = 0;
	return (DWORD)wcslen(buffer);
}

DWORD GetModuleFileNameW(HMODULE module, LPWSTR buffer, DWORD len)
{
	char path[PATH_MAX];
	if (GetModuleFileName(module, path, sizeof(path)) == 0)
		return 0;
	int n = MultiByteToWideChar(CP_UTF8, 0, path, -1, buffer, (int)len);
	return n > 0 ? (DWORD)(n - 1) : 0;
}

int __argc = 0;
char** __argv = nullptr;

//-----------------------------------------------------------------------------
// C runtime file functions with path translation
//-----------------------------------------------------------------------------
#undef fopen
FILE* Win32Shim_fopen(const char* path, const char* mode)
{
	std::string p = Win32Shim_TranslatePath(path);
	// Windows text/binary mode flags: 't' is not understood by the C library.
	std::string m;
	for (const char* c = mode; c && *c; ++c)
	{
		if (*c != 't')
			m += *c;
	}
	return fopen(p.c_str(), m.c_str());
}

int Win32Shim_open(const char* path, int flags, ...)
{
	int mode = 0;
	if (flags & O_CREAT)
	{
		va_list args;
		va_start(args, flags);
		mode = va_arg(args, int);
		va_end(args);
	}
	std::string p = Win32Shim_TranslatePath(path);
	// Windows permission bits are only read/write for the owner.
	if (mode)
		mode = 0644;
	return open(p.c_str(), flags, mode);
}

int Win32Shim_access(const char* path, int mode)
{
	return access(Win32Shim_TranslatePath(path).c_str(), mode);
}

int Win32Shim_unlink(const char* path)
{
	return unlink(Win32Shim_TranslatePath(path).c_str());
}

int Win32Shim_mkdir(const char* path)
{
	return mkdir(Win32Shim_TranslatePath(path).c_str(), 0755);
}

int Win32Shim_chdir(const char* path)
{
	return chdir(Win32Shim_TranslatePath(path).c_str());
}

int Win32Shim_rmdir(const char* path)
{
	return rmdir(Win32Shim_TranslatePath(path).c_str());
}
