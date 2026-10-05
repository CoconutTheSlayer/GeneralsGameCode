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

// Deterministic transcendental functions.
//
// Lockstep multiplayer and replays need every machine to compute bit identical results. Basic IEEE
// arithmetic and sqrt are exact on every 64 bit CPU (with floating point contraction off), but sin,
// cos, pow and the like come from each platform's C library and differ in their last bits. This
// header is included in front of every source file (see cmake) and sends those calls to the musl
// implementations in Dependencies/DetMath, which only use basic arithmetic, so all platforms agree.

#pragma once

#ifdef __cplusplus
#include <cmath>
#endif
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

float rts_sinf(float);
float rts_cosf(float);
float rts_tanf(float);
float rts_asinf(float);
float rts_acosf(float);
float rts_atanf(float);
float rts_atan2f(float, float);
float rts_powf(float, float);
float rts_expf(float);
float rts_logf(float);
float rts_log10f(float);
float rts_sinhf(float);
float rts_coshf(float);
float rts_tanhf(float);
float rts_expm1f(float);
double rts_sin(double);
double rts_cos(double);
double rts_tan(double);
double rts_asin(double);
double rts_acos(double);
double rts_atan(double);
double rts_atan2(double, double);
double rts_pow(double, double);
double rts_exp(double);
double rts_log(double);
double rts_log10(double);

#ifdef __cplusplus
}

// The float overloads C++ adds for these names keep their float results.
inline float rts_sin(float x) { return rts_sinf(x); }
inline float rts_cos(float x) { return rts_cosf(x); }
inline float rts_tan(float x) { return rts_tanf(x); }
inline float rts_asin(float x) { return rts_asinf(x); }
inline float rts_acos(float x) { return rts_acosf(x); }
inline float rts_atan(float x) { return rts_atanf(x); }
inline float rts_atan2(float y, float x) { return rts_atan2f(y, x); }
inline float rts_pow(float x, float y) { return rts_powf(x, y); }
inline float rts_exp(float x) { return rts_expf(x); }
inline float rts_log(float x) { return rts_logf(x); }
inline float rts_log10(float x) { return rts_log10f(x); }
// Mixed and integer arguments promote to double, as with the standard overloads.
template <class A, class B> inline double rts_atan2(A y, B x) { return rts_atan2((double)y, (double)x); }
template <class A, class B> inline double rts_pow(A x, B y) { return rts_pow((double)x, (double)y); }
template <class A> inline double rts_sin(A x) { return rts_sin((double)x); }
template <class A> inline double rts_cos(A x) { return rts_cos((double)x); }
template <class A> inline double rts_tan(A x) { return rts_tan((double)x); }
template <class A> inline double rts_asin(A x) { return rts_asin((double)x); }
template <class A> inline double rts_acos(A x) { return rts_acos((double)x); }
template <class A> inline double rts_atan(A x) { return rts_atan((double)x); }
template <class A> inline double rts_exp(A x) { return rts_exp((double)x); }
template <class A> inline double rts_log(A x) { return rts_log((double)x); }
template <class A> inline double rts_log10(A x) { return rts_log10((double)x); }
#endif

// Function-like, so only calls are redirected and other uses of these names are left alone.
#define sinf(x) rts_sinf(x)
#define cosf(x) rts_cosf(x)
#define tanf(x) rts_tanf(x)
#define asinf(x) rts_asinf(x)
#define acosf(x) rts_acosf(x)
#define atanf(x) rts_atanf(x)
#define atan2f(y, x) rts_atan2f(y, x)
#define powf(x, y) rts_powf(x, y)
#define expf(x) rts_expf(x)
#define logf(x) rts_logf(x)
#define log10f(x) rts_log10f(x)
#define sinhf(x) rts_sinhf(x)
#define coshf(x) rts_coshf(x)
#define tanhf(x) rts_tanhf(x)
#define expm1f(x) rts_expm1f(x)
#define sin(x) rts_sin(x)
#define cos(x) rts_cos(x)
#define tan(x) rts_tan(x)
#define asin(x) rts_asin(x)
#define acos(x) rts_acos(x)
#define atan(x) rts_atan(x)
#define atan2(y, x) rts_atan2(y, x)
#define pow(x, y) rts_pow(x, y)
#define exp(x) rts_exp(x)
#define log(x) rts_log(x)
#define log10(x) rts_log10(x)
