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

// Session log: everything the game writes to stdout and stderr also goes to a file in
// ~/Library/Logs/Command and Conquer Generals, and crashes append a stack trace to it.

#include "win32shim.h"

#include <algorithm>
#include <dirent.h>
#include <execinfo.h>
#if defined(__APPLE__)
#include <mach-o/dyld.h>
#endif
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <string>
#include <sys/stat.h>
#if defined(__APPLE__)
#include <sys/sysctl.h>
#else
#include <sys/sysinfo.h>
#endif
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include <vector>

namespace
{
// Logs of each game kept in the log folder, including the current one.
const size_t kKeptLogs = 20;

std::string g_logDir;
std::string g_logPath;
int g_logFd = -1;       // the log file
int g_consoleFd = -1;   // where stderr pointed before, or -1 if output only goes to the log
int g_pipeRead = -1;    // read end of the pipe stdout and stderr write to, when copying to the console
pthread_t g_teeThread;
bool g_teeRunning = false;

void writeAll(int fd, const char* data, size_t size)
{
	while (size > 0)
	{
		ssize_t n = write(fd, data, size);
		if (n < 0)
		{
			if (errno == EINTR)
				continue;
			return;
		}
		data += n;
		size -= (size_t)n;
	}
}

// Copies what arrives through the pipe to the log file and the console.
void* teeThread(void*)
{
	char buffer[16384];
	for (;;)
	{
		ssize_t n = read(g_pipeRead, buffer, sizeof(buffer));
		if (n < 0 && errno == EINTR)
			continue;
		if (n <= 0)
			break;
		writeAll(g_logFd, buffer, (size_t)n);
		writeAll(g_consoleFd, buffer, (size_t)n);
	}
	return nullptr;
}

// Moves what is still in the pipe to the outputs. Only used while crashing, when the copy
// thread may not get to run again.
void drainPipe()
{
	if (g_pipeRead < 0)
		return;
	fcntl(g_pipeRead, F_SETFL, fcntl(g_pipeRead, F_GETFL) | O_NONBLOCK);
	char buffer[4096];
	ssize_t n;
	while ((n = read(g_pipeRead, buffer, sizeof(buffer))) > 0)
	{
		writeAll(g_logFd, buffer, (size_t)n);
		writeAll(g_consoleFd, buffer, (size_t)n);
	}
}

void writeCrash(const char* text)
{
	writeAll(g_logFd, text, strlen(text));
	if (g_consoleFd >= 0)
		writeAll(g_consoleFd, text, strlen(text));
}

void crashHandler(int sig, siginfo_t* info, void*)
{
	fflush(stdout);
	fflush(stderr);
	drainPipe();

	char line[256];
	snprintf(line, sizeof(line), "\n==== CRASH: signal %d (%s), address %p ====\n", sig, strsignal(sig), info ? info->si_addr : nullptr);
	writeCrash(line);
	void* frames[128];
	int count = backtrace(frames, 128);
	backtrace_symbols_fd(frames, count, g_logFd);
	if (g_consoleFd >= 0)
		backtrace_symbols_fd(frames, count, g_consoleFd);
	writeCrash("==== The macOS crash report is in ~/Library/Logs/DiagnosticReports ====\n");
	fsync(g_logFd);

	// Let the default action run so macOS still writes its crash report.
	signal(sig, SIG_DFL);
	raise(sig);
}

void installCrashHandlers()
{
	// Stack overflows need their own stack to report on.
	static char altStack[64 * 1024];
	stack_t ss = {};
	ss.ss_sp = altStack;
	ss.ss_size = sizeof(altStack);
	sigaltstack(&ss, nullptr);

	struct sigaction sa = {};
	sa.sa_sigaction = crashHandler;
	sa.sa_flags = SA_SIGINFO | SA_ONSTACK | SA_RESETHAND;
	sigemptyset(&sa.sa_mask);
	for (int sig : { SIGSEGV, SIGBUS, SIGILL, SIGFPE, SIGABRT, SIGTRAP })
		sigaction(sig, &sa, nullptr);
}

void stopTee()
{
	fflush(stdout);
	fflush(stderr);
	if (!g_teeRunning)
		return;
	// Point stdout and stderr back at the console; the pipe then has no writers left and the
	// copy thread ends after writing everything.
	dup2(g_consoleFd, STDOUT_FILENO);
	dup2(g_consoleFd, STDERR_FILENO);
	pthread_join(g_teeThread, nullptr);
	g_teeRunning = false;
}

std::string sysctlString(const char* name)
{
#if !defined(__APPLE__)
	// Linux: the CPU model from /proc/cpuinfo, the OS from /etc/os-release.
	std::string key = strcmp(name, "machdep.cpu.brand_string") == 0 ? "model name" : "PRETTY_NAME";
	FILE* f = fopen(key == "model name" ? "/proc/cpuinfo" : "/etc/os-release", "r");
	if (f == nullptr)
		return "unknown";
	char line[512];
	std::string value = "unknown";
	while (fgets(line, sizeof(line), f))
	{
		if (strncmp(line, key.c_str(), key.size()) == 0)
		{
			const char* v = strpbrk(line + key.size(), ":=");
			if (v)
			{
				value = v + 1;
				while (!value.empty() && (value.back() == '\n' || value.back() == '"'))
					value.pop_back();
				while (!value.empty() && (value[0] == ' ' || value[0] == '\t' || value[0] == '"'))
					value.erase(0, 1);
			}
			break;
		}
	}
	fclose(f);
	return value;
#else
	char value[256] = {};
	size_t size = sizeof(value) - 1;
	if (sysctlbyname(name, value, &size, nullptr, 0) != 0)
		return "unknown";
	return value;
#endif
}

// Deletes the oldest logs of this game so that 'keep' remain.
void pruneLogs(const std::string& prefix, size_t keep)
{
	DIR* dir = opendir(g_logDir.c_str());
	if (!dir)
		return;
	std::vector<std::string> logs;
	while (dirent* entry = readdir(dir))
	{
		std::string name = entry->d_name;
		if (name.compare(0, prefix.size(), prefix) == 0 && name.size() > 4 && name.compare(name.size() - 4, 4, ".log") == 0
			&& name.find("latest") == std::string::npos)
			logs.push_back(name);
	}
	closedir(dir);
	// Names start with the date and time, so they sort by age.
	std::sort(logs.begin(), logs.end());
	for (size_t i = 0; i + keep < logs.size(); ++i)
		unlink((g_logDir + "/" + logs[i]).c_str());
}
} // namespace

void Win32Shim_StartSessionLog(const char* appName, const char* version)
{
	if (g_logFd >= 0 || getenv("GENERALS_NO_LOG"))
		return;
	if (!Win32Shim_GetLogDirectory())
		return;

	time_t now = time(nullptr);
	struct tm local;
	localtime_r(&now, &local);
	char stamp[64];
	strftime(stamp, sizeof(stamp), "%Y-%m-%d_%H-%M-%S", &local);
	std::string prefix = std::string(appName) + "-";
	pruneLogs(prefix, kKeptLogs - 1);
	g_logPath = g_logDir + "/" + prefix + stamp + "-" + std::to_string(getpid()) + ".log";
	g_logFd = open(g_logPath.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
	if (g_logFd < 0)
		return;
	std::string latest = g_logDir + "/" + appName + "-latest.log";
	unlink(latest.c_str());
	symlink(g_logPath.c_str(), latest.c_str());

	// Output goes only to the log when nobody would see it (an application bundle started from
	// Finder writes to /dev/null). Otherwise it is copied, so the terminal or a redirection still
	// gets everything.
	struct stat st;
	bool discarded = fstat(STDERR_FILENO, &st) != 0 || (S_ISCHR(st.st_mode) && !isatty(STDERR_FILENO));
	fflush(stdout);
	fflush(stderr);
	int pipeFds[2];
	if (!discarded && pipe(pipeFds) == 0)
	{
		g_consoleFd = fcntl(STDERR_FILENO, F_DUPFD_CLOEXEC, 0);
		g_pipeRead = pipeFds[0];
		fcntl(g_pipeRead, F_SETFD, FD_CLOEXEC);
		dup2(pipeFds[1], STDOUT_FILENO);
		dup2(pipeFds[1], STDERR_FILENO);
		close(pipeFds[1]);
		g_teeRunning = pthread_create(&g_teeThread, nullptr, teeThread, nullptr) == 0;
		atexit(stopTee);
	}
	else
	{
		dup2(g_logFd, STDOUT_FILENO);
		dup2(g_logFd, STDERR_FILENO);
	}
	// stdout is fully buffered when it is not a terminal; keep the order with stderr.
	setvbuf(stdout, nullptr, _IOLBF, 0);
	installCrashHandlers();

	char date[64];
	strftime(date, sizeof(date), "%Y-%m-%d %H:%M:%S %Z", &local);
	struct utsname uts;
	uname(&uts);
	uint64_t memory = 0;
#if defined(__APPLE__)
	size_t size = sizeof(memory);
	sysctlbyname("hw.memsize", &memory, &size, nullptr, 0);
#else
	struct sysinfo si;
	if (sysinfo(&si) == 0)
		memory = (uint64_t)si.totalram * si.mem_unit;
#endif
	fprintf(stderr,
		"==== %s session log ====\n"
		"Started:  %s (pid %d)\n"
		"Version:  %s\n"
		"macOS:    %s (%s, Darwin %s)\n"
		"CPU:      %s, %s cores, %.1f GB memory\n"
		"Command:  %s\n"
		"Log:      %s\n\n",
		appName, date, (int)getpid(), version, sysctlString("kern.osproductversion").c_str(), sysctlString("kern.osversion").c_str(),
		uts.release, sysctlString("machdep.cpu.brand_string").c_str(), std::to_string(sysconf(_SC_NPROCESSORS_ONLN)).c_str(),
		memory / (1024.0 * 1024.0 * 1024.0), GetCommandLine(), g_logPath.c_str());
}

const char* Win32Shim_GetLogDirectory()
{
	// The game's debug log asks from a static constructor, before the session log starts.
	if (g_logDir.empty())
	{
		const char* home = getenv("HOME");
		if (!home)
			return nullptr;
		std::string dir = std::string(home) + "/Library/Logs/Command and Conquer Generals";
		mkdir((std::string(home) + "/Library/Logs").c_str(), 0755);
		mkdir(dir.c_str(), 0755);
		g_logDir = dir;
	}
	return g_logDir.c_str();
}

const char* Win32Shim_GetExtraDataDirectory()
{
	static std::string dir;
	static bool resolved = false;
	if (!resolved)
	{
		resolved = true;
		struct stat st;
		char exe[PATH_MAX];
#if defined(__APPLE__)
		uint32_t size = sizeof(exe);
		if (_NSGetExecutablePath(exe, &size) == 0)
#else
		ssize_t len = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
		if (len > 0 && ((exe[len] = 0), true))
#endif
		{
			char real[PATH_MAX];
			if (realpath(exe, real))
			{
				std::string path = real;
				path = path.substr(0, path.rfind('/')) + "/../Resources/GameData";
				if (stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode))
					dir = path;
			}
		}
#ifdef GENERALS_SOURCE_GAMEDATA_DIR
		if (dir.empty() && stat(GENERALS_SOURCE_GAMEDATA_DIR, &st) == 0 && S_ISDIR(st.st_mode))
			dir = GENERALS_SOURCE_GAMEDATA_DIR;
#endif
	}
	return dir.empty() ? nullptr : dir.c_str();
}
