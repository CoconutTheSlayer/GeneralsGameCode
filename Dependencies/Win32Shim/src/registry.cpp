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

// Registry emulation backed by a text file, plus GetPrivateProfile* INI helpers.
//
// File format (registry.txt), one value per line:
//   <key path>|<value name>|<type>|<hex encoded data>
// Key paths are stored lower case with the root prefixed, e.g. "hklm\software\electronic arts".

#include <windows.h>
#include "win32shim_internal.h"

#include <algorithm>
#include <fstream>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include <sys/stat.h>

namespace
{

struct RegValue
{
	DWORD type = REG_NONE;
	std::vector<BYTE> data;
};

struct RegKey
{
	std::string path; // lower case, backslash separated
};

std::mutex g_regMutex;
bool g_regLoaded = false;
// key path -> (value name lower case -> (original name, value))
std::map<std::string, std::map<std::string, std::pair<std::string, RegValue>>> g_registry;
std::set<std::string> g_regKeys;

std::string toLower(std::string s)
{
	std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return (char)tolower(c); });
	return s;
}

std::string rootName(HKEY key)
{
	if (key == HKEY_LOCAL_MACHINE)
		return "hklm";
	if (key == HKEY_CURRENT_USER)
		return "hkcu";
	if (key == HKEY_CLASSES_ROOT)
		return "hkcr";
	if (key == HKEY_USERS)
		return "hku";
	return std::string();
}

std::string normalizeSubKey(const char* subKey)
{
	std::string s = subKey ? subKey : "";
	for (char& c : s)
	{
		if (c == '/')
			c = '\\';
	}
	while (!s.empty() && s.front() == '\\')
		s.erase(s.begin());
	while (!s.empty() && s.back() == '\\')
		s.pop_back();
	// Treat 32 bit registry redirection as the same location.
	std::string lower = toLower(s);
	const std::string wow = "software\\wow6432node";
	if (lower.compare(0, wow.size(), wow) == 0)
		s = "Software" + s.substr(wow.size());
	return toLower(s);
}

std::string keyPath(HKEY key, const char* subKey)
{
	std::string base = rootName(key);
	if (base.empty())
	{
		RegKey* k = reinterpret_cast<RegKey*>(key);
		if (k == nullptr)
			return std::string();
		base = k->path;
	}
	std::string sub = normalizeSubKey(subKey);
	if (sub.empty())
		return base;
	return base + "\\" + sub;
}

std::string registryFile()
{
	return Win32Shim_UserDataDirectory() + "/registry.txt";
}

std::string hexEncode(const std::vector<BYTE>& data)
{
	static const char digits[] = "0123456789abcdef";
	std::string out;
	out.reserve(data.size() * 2);
	for (BYTE b : data)
	{
		out.push_back(digits[b >> 4]);
		out.push_back(digits[b & 15]);
	}
	return out;
}

std::vector<BYTE> hexDecode(const std::string& s)
{
	std::vector<BYTE> out;
	for (size_t i = 0; i + 1 < s.size(); i += 2)
		out.push_back((BYTE)strtoul(s.substr(i, 2).c_str(), nullptr, 16));
	return out;
}

void addKeyAndParents(const std::string& path)
{
	std::string p = path;
	for (;;)
	{
		g_regKeys.insert(p);
		size_t slash = p.rfind('\\');
		if (slash == std::string::npos)
			break;
		p = p.substr(0, slash);
	}
}

void setString(const std::string& key, const std::string& name, const std::string& value)
{
	RegValue v;
	v.type = REG_SZ;
	v.data.assign(value.begin(), value.end());
	v.data.push_back(0);
	g_registry[key][toLower(name)] = std::make_pair(name, v);
	addKeyAndParents(key);
}

void setDword(const std::string& key, const std::string& name, DWORD value)
{
	RegValue v;
	v.type = REG_DWORD;
	v.data.resize(4);
	memcpy(v.data.data(), &value, 4);
	g_registry[key][toLower(name)] = std::make_pair(name, v);
	addKeyAndParents(key);
}

void installDefaults()
{
	// Values the game expects an installer to have written.
	std::string installPath;
	if (const char* env = getenv("GENERALS_INSTALL_PATH"))
		installPath = env;
	else
	{
		char cwd[PATH_MAX];
		if (getcwd(cwd, sizeof(cwd)))
			installPath = cwd;
	}
	if (!installPath.empty() && installPath.back() != '/')
		installPath += '/';

	const std::string zh = "hklm\\software\\electronic arts\\ea games\\command and conquer generals zero hour";
	const std::string gen = "hklm\\software\\electronic arts\\ea games\\generals";
	if (!g_registry.count(zh))
	{
		setString(zh, "InstallPath", installPath);
		setString(zh, "Language", "english");
		setString(zh, "MapPackVersion", "65536");
		setDword(zh, "Version", 65540);
		setString(zh, "Proxy", "");
		setString(zh, "ERGC", "");
	}
	if (!g_registry.count(gen))
	{
		setString(gen, "InstallPath", installPath);
		setString(gen, "Language", "english");
		setString(gen, "MapPackVersion", "65536");
		setDword(gen, "Version", 65540);
		setString(gen, "ERGC", "");
	}
}

void loadRegistry()
{
	if (g_regLoaded)
		return;
	g_regLoaded = true;
	std::ifstream in(registryFile());
	std::string line;
	while (std::getline(in, line))
	{
		std::vector<std::string> parts;
		std::stringstream ss(line);
		std::string part;
		while (std::getline(ss, part, '|'))
			parts.push_back(part);
		if (parts.size() < 3)
			continue;
		RegValue v;
		v.type = (DWORD)strtoul(parts[2].c_str(), nullptr, 10);
		if (parts.size() > 3)
			v.data = hexDecode(parts[3]);
		g_registry[parts[0]][toLower(parts[1])] = std::make_pair(parts[1], v);
		addKeyAndParents(parts[0]);
	}
	installDefaults();
}

void saveRegistry()
{
	std::ofstream out(registryFile(), std::ios::trunc);
	for (const auto& key : g_registry)
	{
		for (const auto& value : key.second)
			out << key.first << '|' << value.second.first << '|' << value.second.second.type << '|' << hexEncode(value.second.second.data) << '\n';
	}
}

HKEY makeKeyHandle(const std::string& path)
{
	RegKey* k = new RegKey();
	k->path = path;
	return reinterpret_cast<HKEY>(k);
}

} // namespace

std::string Win32Shim_UserDataDirectory()
{
	static std::string dir;
	if (dir.empty())
	{
		const char* home = getenv("HOME");
		dir = std::string(home ? home : "/tmp") + "/Library/Application Support/GeneralsZH";
		mkdir(dir.c_str(), 0755);
	}
	return dir;
}

LONG RegOpenKeyEx(HKEY key, LPCSTR subKey, DWORD, REGSAM, PHKEY result)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	std::string path = keyPath(key, subKey);
	if (path.empty() || !g_regKeys.count(path))
	{
		if (result)
			*result = nullptr;
		return ERROR_FILE_NOT_FOUND;
	}
	*result = makeKeyHandle(path);
	return ERROR_SUCCESS;
}

LONG RegOpenKey(HKEY key, LPCSTR subKey, PHKEY result)
{
	return RegOpenKeyEx(key, subKey, 0, KEY_READ, result);
}

LONG RegCreateKeyEx(HKEY key, LPCSTR subKey, DWORD, LPSTR, DWORD, REGSAM, LPSECURITY_ATTRIBUTES, PHKEY result, LPDWORD disposition)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	std::string path = keyPath(key, subKey);
	if (path.empty())
		return ERROR_INVALID_HANDLE;
	bool existed = g_regKeys.count(path) != 0;
	addKeyAndParents(path);
	if (disposition)
		*disposition = existed ? REG_OPENED_EXISTING_KEY : REG_CREATED_NEW_KEY;
	*result = makeKeyHandle(path);
	return ERROR_SUCCESS;
}

LONG RegCreateKey(HKEY key, LPCSTR subKey, PHKEY result)
{
	return RegCreateKeyEx(key, subKey, 0, nullptr, 0, KEY_ALL_ACCESS, nullptr, result, nullptr);
}

LONG RegCloseKey(HKEY key)
{
	if (rootName(key).empty())
		delete reinterpret_cast<RegKey*>(key);
	return ERROR_SUCCESS;
}

LONG RegQueryValueEx(HKEY key, LPCSTR name, LPDWORD, LPDWORD type, LPBYTE data, LPDWORD dataLen)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	std::string path = keyPath(key, nullptr);
	auto k = g_registry.find(path);
	if (k == g_registry.end())
		return ERROR_FILE_NOT_FOUND;
	auto v = k->second.find(toLower(name ? name : ""));
	if (v == k->second.end())
		return ERROR_FILE_NOT_FOUND;
	const RegValue& value = v->second.second;
	if (type)
		*type = value.type;
	if (dataLen == nullptr)
		return data ? ERROR_INVALID_PARAMETER : ERROR_SUCCESS;
	DWORD size = (DWORD)value.data.size();
	if (data == nullptr)
	{
		*dataLen = size;
		return ERROR_SUCCESS;
	}
	if (*dataLen < size)
	{
		*dataLen = size;
		return ERROR_MORE_DATA;
	}
	memcpy(data, value.data.data(), size);
	*dataLen = size;
	return ERROR_SUCCESS;
}

LONG RegSetValueEx(HKEY key, LPCSTR name, DWORD, DWORD type, const BYTE* data, DWORD dataLen)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	std::string path = keyPath(key, nullptr);
	if (path.empty())
		return ERROR_INVALID_HANDLE;
	RegValue v;
	v.type = type;
	if (data && dataLen)
		v.data.assign(data, data + dataLen);
	std::string n = name ? name : "";
	g_registry[path][toLower(n)] = std::make_pair(n, v);
	addKeyAndParents(path);
	saveRegistry();
	return ERROR_SUCCESS;
}

LONG RegDeleteValue(HKEY key, LPCSTR name)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	std::string path = keyPath(key, nullptr);
	auto k = g_registry.find(path);
	if (k == g_registry.end() || k->second.erase(toLower(name ? name : "")) == 0)
		return ERROR_FILE_NOT_FOUND;
	saveRegistry();
	return ERROR_SUCCESS;
}

LONG RegDeleteKey(HKEY key, LPCSTR subKey)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	std::string path = keyPath(key, subKey);
	g_registry.erase(path);
	g_regKeys.erase(path);
	saveRegistry();
	return ERROR_SUCCESS;
}

namespace
{
std::vector<std::string> childKeys(const std::string& path)
{
	std::vector<std::string> out;
	std::string prefix = path + "\\";
	for (const std::string& k : g_regKeys)
	{
		if (k.compare(0, prefix.size(), prefix) == 0 && k.find('\\', prefix.size()) == std::string::npos)
			out.push_back(k.substr(prefix.size()));
	}
	return out;
}
} // namespace

LONG RegEnumKeyEx(HKEY key, DWORD index, LPSTR name, LPDWORD nameLen, LPDWORD, LPSTR, LPDWORD, PFILETIME)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	std::vector<std::string> children = childKeys(keyPath(key, nullptr));
	if (index >= children.size())
		return ERROR_NO_MORE_ITEMS;
	const std::string& child = children[index];
	if (child.size() >= *nameLen)
		return ERROR_MORE_DATA;
	strcpy(name, child.c_str());
	*nameLen = (DWORD)child.size();
	return ERROR_SUCCESS;
}

LONG RegEnumKey(HKEY key, DWORD index, LPSTR name, DWORD nameLen)
{
	return RegEnumKeyEx(key, index, name, &nameLen, nullptr, nullptr, nullptr, nullptr);
}

LONG RegEnumValue(HKEY key, DWORD index, LPSTR name, LPDWORD nameLen, LPDWORD, LPDWORD type, LPBYTE data, LPDWORD dataLen)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	auto k = g_registry.find(keyPath(key, nullptr));
	if (k == g_registry.end() || index >= k->second.size())
		return ERROR_NO_MORE_ITEMS;
	auto it = k->second.begin();
	std::advance(it, index);
	const std::string& n = it->second.first;
	const RegValue& v = it->second.second;
	if (n.size() >= *nameLen)
		return ERROR_MORE_DATA;
	strcpy(name, n.c_str());
	*nameLen = (DWORD)n.size();
	if (type)
		*type = v.type;
	if (dataLen)
	{
		if (data && *dataLen >= v.data.size())
			memcpy(data, v.data.data(), v.data.size());
		*dataLen = (DWORD)v.data.size();
	}
	return ERROR_SUCCESS;
}

LONG RegQueryInfoKey(HKEY key, LPSTR, LPDWORD, LPDWORD, LPDWORD subKeys, LPDWORD maxSubKeyLen, LPDWORD, LPDWORD values, LPDWORD maxValueNameLen, LPDWORD maxValueLen, LPDWORD, PFILETIME)
{
	std::lock_guard<std::mutex> lock(g_regMutex);
	loadRegistry();
	std::string path = keyPath(key, nullptr);
	std::vector<std::string> children = childKeys(path);
	if (subKeys)
		*subKeys = (DWORD)children.size();
	if (maxSubKeyLen)
	{
		DWORD m = 0;
		for (const auto& c : children)
			m = std::max<DWORD>(m, (DWORD)c.size());
		*maxSubKeyLen = m;
	}
	auto k = g_registry.find(path);
	DWORD count = 0, maxName = 0, maxData = 0;
	if (k != g_registry.end())
	{
		for (const auto& v : k->second)
		{
			++count;
			maxName = std::max<DWORD>(maxName, (DWORD)v.second.first.size());
			maxData = std::max<DWORD>(maxData, (DWORD)v.second.second.data.size());
		}
	}
	if (values)
		*values = count;
	if (maxValueNameLen)
		*maxValueNameLen = maxName;
	if (maxValueLen)
		*maxValueLen = maxData;
	return ERROR_SUCCESS;
}

//-----------------------------------------------------------------------------
// INI files
//-----------------------------------------------------------------------------
namespace
{
typedef std::vector<std::pair<std::string, std::vector<std::pair<std::string, std::string>>>> IniData;

std::string trim(const std::string& s)
{
	size_t b = s.find_first_not_of(" \t\r\n");
	if (b == std::string::npos)
		return std::string();
	size_t e = s.find_last_not_of(" \t\r\n");
	return s.substr(b, e - b + 1);
}

IniData readIni(const std::string& path)
{
	IniData data;
	std::ifstream in(path);
	std::string line;
	while (std::getline(in, line))
	{
		line = trim(line);
		if (line.empty() || line[0] == ';')
			continue;
		if (line[0] == '[')
		{
			size_t end = line.find(']');
			data.push_back(std::make_pair(line.substr(1, end == std::string::npos ? std::string::npos : end - 1), std::vector<std::pair<std::string, std::string>>()));
			continue;
		}
		size_t eq = line.find('=');
		if (eq == std::string::npos || data.empty())
			continue;
		data.back().second.push_back(std::make_pair(trim(line.substr(0, eq)), trim(line.substr(eq + 1))));
	}
	return data;
}

std::string iniPath(LPCSTR file)
{
	std::string p = Win32Shim_TranslatePath(file);
	if (p.find('/') == std::string::npos)
		p = Win32Shim_UserDataDirectory() + "/" + p;
	return p;
}
} // namespace

DWORD GetPrivateProfileString(LPCSTR app, LPCSTR key, LPCSTR def, LPSTR out, DWORD size, LPCSTR file)
{
	if (size == 0)
		return 0;
	IniData data = readIni(iniPath(file));
	std::string result;
	bool found = false;
	if (app == nullptr)
	{
		// List section names, double null terminated.
		for (const auto& s : data)
		{
			result += s.first;
			result.push_back(0);
		}
		found = true;
	}
	else
	{
		for (const auto& s : data)
		{
			if (strcasecmp(s.first.c_str(), app) != 0)
				continue;
			if (key == nullptr)
			{
				for (const auto& kv : s.second)
				{
					result += kv.first;
					result.push_back(0);
				}
				found = true;
			}
			else
			{
				for (const auto& kv : s.second)
				{
					if (strcasecmp(kv.first.c_str(), key) == 0)
					{
						result = kv.second;
						found = true;
						break;
					}
				}
			}
			break;
		}
	}
	if (!found)
		result = def ? def : "";
	DWORD n = (DWORD)std::min<size_t>(result.size(), size - 1);
	memcpy(out, result.data(), n);
	out[n] = 0;
	return n;
}

UINT GetPrivateProfileInt(LPCSTR app, LPCSTR key, INT def, LPCSTR file)
{
	char buffer[64];
	char defStr[32];
	snprintf(defStr, sizeof(defStr), "%d", def);
	GetPrivateProfileString(app, key, defStr, buffer, sizeof(buffer), file);
	return (UINT)strtol(buffer, nullptr, 10);
}

BOOL WritePrivateProfileString(LPCSTR app, LPCSTR key, LPCSTR str, LPCSTR file)
{
	std::string path = iniPath(file);
	IniData data = readIni(path);
	auto section = std::find_if(data.begin(), data.end(), [app](const auto& s) { return strcasecmp(s.first.c_str(), app) == 0; });
	if (key == nullptr)
	{
		if (section != data.end())
			data.erase(section);
	}
	else
	{
		if (section == data.end())
		{
			data.push_back(std::make_pair(std::string(app), std::vector<std::pair<std::string, std::string>>()));
			section = data.end() - 1;
		}
		auto& entries = section->second;
		auto entry = std::find_if(entries.begin(), entries.end(), [key](const auto& kv) { return strcasecmp(kv.first.c_str(), key) == 0; });
		if (str == nullptr)
		{
			if (entry != entries.end())
				entries.erase(entry);
		}
		else if (entry != entries.end())
			entry->second = str;
		else
			entries.push_back(std::make_pair(std::string(key), std::string(str)));
	}
	std::ofstream out(path, std::ios::trunc);
	for (const auto& s : data)
	{
		out << '[' << s.first << "]\n";
		for (const auto& kv : s.second)
			out << kv.first << '=' << kv.second << '\n';
		out << '\n';
	}
	return TRUE;
}

//-----------------------------------------------------------------------------
// Shell folders
//-----------------------------------------------------------------------------
#include <shlobj.h>

namespace
{
std::string folderForCsidl(int csidl)
{
	const char* home = getenv("HOME");
	std::string h = home ? home : "/tmp";
	switch (csidl & 0xFF)
	{
	case CSIDL_PERSONAL: return h + "/Documents";
	case CSIDL_DESKTOP:
	case CSIDL_DESKTOPDIRECTORY: return h + "/Desktop";
	case CSIDL_APPDATA:
	case CSIDL_LOCAL_APPDATA:
	case CSIDL_COMMON_APPDATA: return h + "/Library/Application Support";
	case CSIDL_PROGRAM_FILES: return "/Applications";
	default: return h;
	}
}
} // namespace

BOOL SHGetSpecialFolderPath(HWND, LPSTR path, int csidl, BOOL create)
{
	std::string folder = folderForCsidl(csidl);
	if (create)
		mkdir(folder.c_str(), 0755);
	strlcpy(path, folder.c_str(), MAX_PATH);
	return TRUE;
}

HRESULT SHGetFolderPath(HWND hwnd, int csidl, HANDLE, DWORD, LPSTR path)
{
	return SHGetSpecialFolderPath(hwnd, path, csidl, (csidl & CSIDL_FLAG_CREATE) != 0) ? S_OK : E_FAIL;
}

HRESULT SHGetSpecialFolderLocation(HWND, int csidl, LPITEMIDLIST* pidl)
{
	LPITEMIDLIST item = (LPITEMIDLIST)malloc(sizeof(ITEMIDLIST));
	strlcpy(item->path, folderForCsidl(csidl).c_str(), MAX_PATH);
	*pidl = item;
	return S_OK;
}

BOOL SHGetPathFromIDList(LPCITEMIDLIST pidl, LPSTR path)
{
	if (pidl == nullptr)
		return FALSE;
	strlcpy(path, pidl->path, MAX_PATH);
	return TRUE;
}
