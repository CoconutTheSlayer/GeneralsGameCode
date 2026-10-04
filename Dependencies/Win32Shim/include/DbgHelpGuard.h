// Win32Shim: crash dump support is not available on macOS.
#pragma once
class DbgHelpGuard
{
public:
	void activate() {}
	void deactivate() {}
};
