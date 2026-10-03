// Win32Shim forwarding header.
#pragma once
#include <windows.h>
#include <fcntl.h>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>
#define _O_RDONLY O_RDONLY
#define _O_WRONLY O_WRONLY
#define _O_RDWR O_RDWR
#define _O_CREAT O_CREAT
#define _O_TRUNC O_TRUNC
#define _O_APPEND O_APPEND
#define _O_EXCL O_EXCL
#define _O_BINARY 0
#define _O_TEXT 0
#define O_BINARY 0
#define O_TEXT 0
#define _S_IREAD S_IRUSR
#define _S_IWRITE S_IWUSR
#define _open open
#define _close close
#define _read read
#define _write write
#define _lseek lseek
#define _tell(fd) lseek((fd), 0, SEEK_CUR)
#define _chmod chmod
inline long _filelength(int fd) { struct stat st; return fstat(fd, &st) == 0 ? (long)st.st_size : -1L; }
#define filelength _filelength
struct _finddata_t { unsigned attrib; time_t time_create; time_t time_access; time_t time_write; uint32_t size; char name[260]; };
#define _A_NORMAL 0x00
#define _A_RDONLY 0x01
#define _A_HIDDEN 0x02
#define _A_SYSTEM 0x04
#define _A_SUBDIR 0x10
#define _A_ARCH 0x20
intptr_t _findfirst(const char* spec, struct _finddata_t* data);
int _findnext(intptr_t handle, struct _finddata_t* data);
int _findclose(intptr_t handle);
