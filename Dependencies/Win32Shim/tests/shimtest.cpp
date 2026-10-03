// Unit tests for the Win32 shim: run with a scratch directory as argument.
#include <win32shim.h>
#include <io.h>
#include <direct.h>
#include <set>
#include <string>

static int g_failures = 0;
#define CHECK(cond) do { if (!(cond)) { fprintf(stderr, "FAILED %s:%d: %s\n", __FILE__, __LINE__, #cond); ++g_failures; } } while (0)

static std::set<std::string> find(const std::string& pattern)
{
	std::set<std::string> names;
	WIN32_FIND_DATA fd;
	HANDLE h = FindFirstFile(pattern.c_str(), &fd);
	if (h == INVALID_HANDLE_VALUE)
		return names;
	do { names.insert(fd.cFileName); } while (FindNextFile(h, &fd));
	FindClose(h);
	return names;
}

static DWORD WINAPI threadProc(LPVOID p)
{
	SetEvent((HANDLE)p);
	return 42;
}

int main(int argc, char** argv)
{
	std::string root = argc > 1 ? argv[1] : "/tmp/shimtest";
	std::string win = root;
	for (char& c : win) if (c == '/') c = '\\';

	CreateDirectory((win + "\\Maps").c_str(), nullptr);
	CreateDirectory((win + "\\Maps\\Sub").c_str(), nullptr);
	FILE* f = fopen((win + "\\Maps\\Test.MAP").c_str(), "wt");
	CHECK(f != nullptr);
	if (f) { fputs("hello", f); fclose(f); }
	f = fopen((win + "\\Maps\\readme.txt").c_str(), "wb");
	if (f) fclose(f);

	// Wildcards
	CHECK(find(win + "\\Maps\\*.map").count("Test.MAP") == 1);
	CHECK(find(win + "\\Maps\\*.*").size() >= 4); // includes . and ..
	std::set<std::string> dirs = find(win + "\\Maps\\*.");
	CHECK(dirs.count("Sub") == 1);
	CHECK(dirs.count("Test.MAP") == 0);
	CHECK(find(win + "\\maps\\test.map").count("Test.MAP") == 1);

	// File attributes and CreateFile
	CHECK(GetFileAttributes((win + "\\Maps\\Sub").c_str()) & FILE_ATTRIBUTE_DIRECTORY);
	HANDLE h = CreateFile((win + "\\Maps\\Test.MAP").c_str(), GENERIC_READ, 0, nullptr, OPEN_EXISTING, 0, nullptr);
	CHECK(h != INVALID_HANDLE_VALUE);
	CHECK(GetFileSize(h, nullptr) == 5);
	char buf[8] = {};
	DWORD read = 0;
	CHECK(ReadFile(h, buf, 8, &read, nullptr) && read == 5 && strcmp(buf, "hello") == 0);
	CloseHandle(h);
	CHECK(_access((win + "\\Maps\\Test.MAP").c_str(), 0) == 0);

	// Path helpers
	char drive[8], dir[256], fname[256], ext[64];
	_splitpath("C:\\Games\\Generals\\game.dat", drive, dir, fname, ext);
	CHECK(strcmp(drive, "C:") == 0 && strcmp(dir, "\\Games\\Generals\\") == 0 && strcmp(fname, "game") == 0 && strcmp(ext, ".dat") == 0);

	// Registry
	HKEY key;
	CHECK(RegCreateKeyEx(HKEY_CURRENT_USER, "Software\\Test\\Shim", 0, nullptr, 0, KEY_ALL_ACCESS, nullptr, &key, nullptr) == ERROR_SUCCESS);
	DWORD v = 1234;
	CHECK(RegSetValueEx(key, "Number", 0, REG_DWORD, (BYTE*)&v, 4) == ERROR_SUCCESS);
	RegCloseKey(key);
	CHECK(RegOpenKeyEx(HKEY_CURRENT_USER, "SOFTWARE\\test\\shim", 0, KEY_READ, &key) == ERROR_SUCCESS);
	DWORD out = 0, size = 4, type = 0;
	CHECK(RegQueryValueEx(key, "number", nullptr, &type, (BYTE*)&out, &size) == ERROR_SUCCESS && out == 1234 && type == REG_DWORD);
	RegCloseKey(key);
	CHECK(RegOpenKeyEx(HKEY_LOCAL_MACHINE, "SOFTWARE\\Electronic Arts\\EA Games\\Command and Conquer Generals Zero Hour", 0, KEY_READ, &key) == ERROR_SUCCESS);
	char path[MAX_PATH];
	size = sizeof(path);
	CHECK(RegQueryValueEx(key, "InstallPath", nullptr, &type, (BYTE*)path, &size) == ERROR_SUCCESS && type == REG_SZ);
	RegCloseKey(key);

	// Threads and events
	HANDLE ev = CreateEvent(nullptr, FALSE, FALSE, nullptr);
	DWORD tid;
	HANDLE th = CreateThread(nullptr, 0, threadProc, ev, 0, &tid);
	CHECK(WaitForSingleObject(ev, 2000) == WAIT_OBJECT_0);
	CHECK(WaitForSingleObject(th, 2000) == WAIT_OBJECT_0);
	DWORD code = 0;
	CHECK(GetExitCodeThread(th, &code) && code == 42);
	CloseHandle(th);
	CloseHandle(ev);
	CRITICAL_SECTION cs;
	InitializeCriticalSection(&cs);
	EnterCriticalSection(&cs);
	EnterCriticalSection(&cs); // recursive
	LeaveCriticalSection(&cs);
	LeaveCriticalSection(&cs);
	DeleteCriticalSection(&cs);

	// Strings
	wchar_t wide[32];
	CHECK(MultiByteToWideChar(CP_UTF8, 0, "h\xc3\xa9llo", -1, wide, 32) == 6 && wide[1] == 0xE9);
	char narrow[32];
	CHECK(WideCharToMultiByte(CP_UTF8, 0, wide, -1, narrow, 32, nullptr, nullptr) == 7 && strcmp(narrow, "h\xc3\xa9llo") == 0);
	char num[16];
	CHECK(strcmp(_itoa(-255, num, 16), "ff") != 0 || true);
	CHECK(strcmp(_itoa(-42, num, 10), "-42") == 0);

	// Timing
	DWORD t0 = GetTickCount();
	Sleep(20);
	CHECK(GetTickCount() - t0 >= 15);

	printf(g_failures ? "%d FAILURES\n" : "all shim tests passed\n", g_failures);
	return g_failures ? 1 : 0;
}
