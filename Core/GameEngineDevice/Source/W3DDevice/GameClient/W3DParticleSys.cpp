/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2025 Electronic Arts Inc.
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

////////////////////////////////////////////////////////////////////////////////
//																																						//
//  (c) 2001-2003 Electronic Arts Inc.																				//
//																																						//
////////////////////////////////////////////////////////////////////////////////

// W3DParticleSys.cpp
// W3D Particle System implementation
// Author: Michael S. Booth, November 2001

#include "Common/GlobalData.h"
#include "GameClient/Color.h"
#include "W3DDevice/GameClient/W3DParticleSys.h"
#include "W3DDevice/GameClient/W3DAssetManager.h"
#include "W3DDevice/GameClient/W3DDisplay.h"
#include "W3DDevice/GameClient/HeightMap.h"
#include "W3DDevice/GameClient/W3DSmudge.h"
#include "W3DDevice/GameClient/W3DSnow.h"
#include "WW3D2/camera.h"
#include "WW3D2/dx8wrapper.h"
#include "WW3D2/dx8vertexbuffer.h"
#include "WW3D2/dx8indexbuffer.h"
#include "WW3D2/vertmaterial.h"
#include "GameLogic/TerrainLogic.h"


//------------------------------------------------------------------------------ Performance Timers
//#include "Common/PerfMetrics.h"
//#include "Common/PerfTimer.h"

//-------------------------------------------------------------------------------------------------


W3DParticleSystemManager::W3DParticleSystemManager()
{
	m_batchParticleAlignment = ParticleSystemInfo::PARTICLE_ALIGNMENT_BILLBOARD;
	m_batchShaderType = ParticleSystemInfo::INVALID_SHADER;

	m_pointGroup = nullptr;
	m_streakLine = nullptr;
	m_posBuffer = nullptr;
	m_RGBABuffer = nullptr;
	m_sizeBuffer = nullptr;
	m_angleBuffer = nullptr;
	m_readyToRender = false;

	m_onScreenParticleCount = 0;

	m_pointGroup = NEW PointGroupClass();
	//m_streakLine = nullptr;
	m_streakLine = NEW StreakLineClass();

	m_posBuffer = NEW_REF( ShareBufferClass<Vector3>, (MAX_POINTS_PER_GROUP, "W3DParticleSystemManager::m_posBuffer") );
	m_RGBABuffer = NEW_REF( ShareBufferClass<Vector4>, (MAX_POINTS_PER_GROUP, "W3DParticleSystemManager::m_RGBABuffer") );
	m_sizeBuffer = NEW_REF( ShareBufferClass<float>, (MAX_POINTS_PER_GROUP, "W3DParticleSystemManager::m_sizeBuffer") );
	m_angleBuffer = NEW_REF( ShareBufferClass<uint8>, (MAX_POINTS_PER_GROUP, "W3DParticleSystemManager::m_angleBuffer") );
}

W3DParticleSystemManager::~W3DParticleSystemManager()
{
	delete m_pointGroup;

//	W3DDisplay::m_3DScene->Remove_Render_Object( m_streakLine );

	if (m_streakLine)
	{
		REF_PTR_RELEASE(m_streakLine);
	}

	REF_PTR_RELEASE(m_posBuffer);
	REF_PTR_RELEASE(m_RGBABuffer);
	REF_PTR_RELEASE(m_sizeBuffer);
	REF_PTR_RELEASE(m_angleBuffer);
}

/**
 * Hack because DoParticles is called from Flush(), which is called
 * multiple times per frame.  We only want to render once.
 * @todo Clean up the flag/Flush hack.
 */
void W3DParticleSystemManager::queueParticleRender()
{
	m_readyToRender = true;
}

/**
 * Nasty hack to render particles last. Called directly by WW3D::Flush()
 */
void DoParticles( RenderInfoClass &rinfo )
{
	if (TheParticleSystemManager)
		TheParticleSystemManager->doParticles(rinfo);
}

void W3DParticleSystemManager::doParticles(RenderInfoClass &rinfo)
{

	if (m_readyToRender == false)
		return;

	// external mechanism must tell us when it's OK to render again...
	m_readyToRender = false;

	//reset each frame
	/// @todo lorenzen sez: this should be debug only:
	m_onScreenParticleCount = 0;

 	const FrustumClass & frustum = rinfo.Camera.Get_Frustum();
	AABoxClass bbox;

	//Get a bounding box around our visible universe.  Bounded by terrain and the sky
	//so much tighter fitting volume than what's actually visible.  This will cull
	//particles falling under the ground.

 	TheTerrainRenderObject->getMaximumVisibleBox(frustum, &bbox, TRUE);

	//@todo lorenzen sez: put these in registers for sure
	Real bcX = bbox.Center.X;
	Real bcY = bbox.Center.Y;
	Real bcZ = bbox.Center.Z;
	Real beX = bbox.Extent.X;
	Real beY = bbox.Extent.Y;
	Real beZ = bbox.Extent.Z;

	unsigned int personalities[MAX_POINTS_PER_GROUP];


	m_fieldParticleCount = 0;

	const Bool drawSmudge = TheSmudgeManager && TheSmudgeManager->getHardwareSupport() && TheGlobalData->m_useHeatEffects;

	if (drawSmudge)
	{
		TheSmudgeManager->resetDraw();
	}

	// Number of particles/points being rendered.
	UnsignedInt pointCount = 0;

	ParticleSystemManager::ParticleSystemList &particleSysList = TheParticleSystemManager->getAllParticleSystems();
	for( ParticleSystemManager::ParticleSystemListIt it = particleSysList.begin(); it != particleSysList.end(); ++it)
	{
		ParticleSystem *sys = (*it);
		if (!sys) {
			continue;
		}

		// only look at particle/point style systems
		if (sys->isUsingDrawables())
			continue;

		// TheSuperHackers @performance Mauller 16/08/2026 Skip processing particle system if no particles are in view.
		UnsignedInt particleCount = 0;
		for (Particle* vp = sys->getFirstParticle(); vp; vp = vp->m_systemNext)
		{
			const Coord3D* pos = vp->getPosition();
			const Real psize = vp->getSize();

			//Test if particle is at the screen or terrain edges.
			if (WWMath::Fabs(pos->x - bcX) > (beX + psize) ||
				WWMath::Fabs(pos->y - bcY) > (beY + psize) ||
				WWMath::Fabs(pos->z - bcZ) > (beZ + psize))
			{
				vp->setIsCulled(true);
				continue;
			}

			vp->setIsCulled(false);
			particleCount++;
		}

		// Particle system has no particles on screen
		if (particleCount == 0)
			continue;

		// Handle smudge type particles
		if (sys->isUsingSmudge())
		{
			if (!drawSmudge)
				continue;

			for (Particle *p = sys->getFirstParticle(); p; p = p->m_systemNext)
			{
				if (p->isCulled())
					continue;

				if (Smudge *smudge = TheSmudgeManager->findSmudge(p))
				{
					// The particle is in view. Draw the smudge!
					smudge->m_draw = true;
				}
			}
			continue;
		}

		// TheSuperHackers @performance Ronin/Mauller 09/08/2026 Implement batched rendering for similar particles.
		// Particles with the same properties will now be batched onto a single texture surface before being drawn.
		// If a different particle type appears before the batch is filled, the previous batch will be drawn first.
		RefCountPtr<TextureClass> texture;
		texture.Assign_No_Add_Ref(W3DDisplay::m_assetManager->Get_Texture(sys->getParticleTypeName().str()));

		const Bool canBatch = sys->isUsingParticles();
		const Bool batchDone = finishedBatch(*sys, texture);
		if (!canBatch || batchDone)
		{
			flushParticleBatch(rinfo, pointCount);
		}

		// setup a new particle batch texture if prior batch was flushed.
		if (canBatch && m_batchTexture == nullptr)
		{
			initializeBatch(*sys, texture);
		}

		UnsignedInt startCount = pointCount;

		// build W3D particle buffer
		Vector3 *posArray = m_posBuffer->Get_Array();
		Real *sizeArray = m_sizeBuffer->Get_Array();
		Vector4 *RGBAArray = m_RGBABuffer->Get_Array();
		uint8 *angleArray = m_angleBuffer->Get_Array();
		const Coord3D *pos;
		const RGBColor *color;
		Real psize;



		//set-up all the per-particle
		for (Particle *p = sys->getFirstParticle(); p; p = p->m_systemNext)
		{
			if (p->isCulled())
				continue;

			pos = p->getPosition();
			psize = p->getSize();

			m_fieldParticleCount += ( sys->getPriority() == AREA_EFFECT && sys->isFieldParticle() );

			//@todo lorenzen sez: use pointer arithmetic for these arrays
			personalities[pointCount] = p->getPersonality();

			posArray[pointCount].X = pos->x;
			posArray[pointCount].Y = pos->y;
			posArray[pointCount].Z = pos->z;

			sizeArray[pointCount] = psize;

			color = p->getColor();
			RGBAArray[pointCount].X = color->red;
			RGBAArray[pointCount].Y = color->green;
			RGBAArray[pointCount].Z = color->blue;
			RGBAArray[pointCount].W = p->getAlpha();

			angleArray[pointCount] = (uint8)(p->getAngle() * 255.0f / (2.0f * PI));

			if (++pointCount == MAX_POINTS_PER_GROUP)
			{
				if (!canBatch)
				{
					break;
				}

				// TheSuperHackers @info The Buffer is full mid-system so draw what we have and carry on with the SAME system.
				// This prevents particles being dropped. Bank the stats first as the flush resets count to 0.
				m_onScreenParticleCount += (pointCount - startCount);
				flushParticleBatch(rinfo, pointCount);
				initializeBatch(*sys, texture);
				startCount = 0;
			}
		}

		if (pointCount == startCount)
		{
			continue;	//this system has no particles to render
		}

		const UnsignedInt volumeParticleDepth = sys->getVolumeParticleDepth();

		// Handle drawing streak type particles.
		if ( sys->isUsingStreak() && (pointCount >= 2) )
		{
			m_streakLine->Reset_Line();

			m_streakLine->Set_Texture( texture.Peek() );
			switch( sys->getShaderType() )
			{
				case ParticleSystemInfo::ADDITIVE:
					m_streakLine->Set_Shader( ShaderClass::_PresetAdditiveSpriteShader );
					break;
				case ParticleSystemInfo::ALPHA:
					m_streakLine->Set_Shader( ShaderClass::_PresetAlphaSpriteShader );
					break;
				case ParticleSystemInfo::ALPHA_TEST:
					m_streakLine->Set_Shader( ShaderClass::_PresetATestSpriteShader );
					break;
				case ParticleSystemInfo::MULTIPLY:
					m_streakLine->Set_Shader( ShaderClass::_PresetMultiplicativeSpriteShader );
					break;
			}

			//UPDATE THE STREAK'S ARRAYS
			m_streakLine->Set_LocsWidthsColors(
				pointCount,
				m_posBuffer->Get_Array(),
				m_sizeBuffer->Get_Array(),
				m_RGBABuffer->Get_Array(),
				&personalities[0]
				);

			//WWASSERT( m_streakLine->Get_Num_Points() == pointCount );

			// This is the happy place for this!
			RGBAArray[0].X = 0;//eliminates the scissor edge on the trailing edge of the streak
			RGBAArray[0].Y = 0;
			RGBAArray[0].Z = 0;
			RGBAArray[0].W = 0;


			//RENDER STREAK!
			m_streakLine->Render( rinfo );
			m_onScreenParticleCount += (pointCount - startCount);
			pointCount = startCount;
		}
		// Handle lone streak type particles by drawing them as regular particles.
		else if (sys->isUsingStreak() && (pointCount == 1))
		{
			m_onScreenParticleCount += (pointCount - startCount);
			initializeBatch(*sys, texture);
			flushParticleBatch(rinfo, pointCount);
			startCount = 0;
		}
		// Handle volumetric type particle systems.
		else if( sys->isUsingVolumeParticles() && volumeParticleDepth > DEFAULT_VOLUME_PARTICLE_DEPTH )
		{
			m_pointGroup->Set_Texture( texture.Peek() );
			m_pointGroup->Set_Flag( PointGroupClass::TRANSFORM, true );	// transform to screen space

			switch( sys->getShaderType() )
			{
				case ParticleSystemInfo::ADDITIVE:
					m_pointGroup->Set_Shader( ShaderClass::_PresetAdditiveSpriteShader );
					break;
				case ParticleSystemInfo::ALPHA:
					m_pointGroup->Set_Shader( ShaderClass::_PresetAlphaSpriteShader );
					break;
				case ParticleSystemInfo::ALPHA_TEST:
					m_pointGroup->Set_Shader( ShaderClass::_PresetATestSpriteShader );
					break;
				case ParticleSystemInfo::MULTIPLY:
					m_pointGroup->Set_Shader( ShaderClass::_PresetMultiplicativeSpriteShader );
					break;
			}

			/// @todo Use both QUADS and TRIS for particles
			m_pointGroup->Set_Point_Mode( PointGroupClass::QUADS );
			m_pointGroup->Set_Arrays( m_posBuffer, m_RGBABuffer, nullptr, m_sizeBuffer, m_angleBuffer, nullptr, pointCount );
			m_pointGroup->Set_Billboard(sys->getParticleAlignment() == ParticleSystemInfo::PARTICLE_ALIGNMENT_BILLBOARD);

			/// @todo Support animated texture particles
			/// @todo lorenzen sez: unimplemented code wastes cpu cycles
			m_pointGroup->Set_Point_Frame( 0 );

			m_pointGroup->RenderVolumeParticle( rinfo, volumeParticleDepth);
			m_onScreenParticleCount += (pointCount - startCount);
			pointCount = startCount;
		}


		/// @todo lorenzen sez: this should be debug only:
		//add particle count to total
		m_onScreenParticleCount += (pointCount - startCount);

	/*
		// draw the wind vector for this particle system on the screen
		UnsignedInt width = TheDisplay->getWidth();
		UnsignedInt height = TheDisplay->getHeight();
		Coord3D worldStart, worldEnd;
		ICoord2D pixelStart, pixelEnd;
		sys->getPosition( &worldStart );
		worldEnd.x = Cos( sys->getWindAngle() ) * 50.0f + worldStart.x;
		worldEnd.y = Sin( sys->getWindAngle() ) * 50.0f + worldStart.y;
		worldEnd.z = worldStart.z;
		TheTacticalView->worldToScreen( &worldStart, &pixelStart );
		TheTacticalView->worldToScreen( &worldEnd, &pixelEnd );
		Color colorStart = GameMakeColor( 255, 255, 255, 255 );
		Color colorEnd = GameMakeColor( 255, 128, 128, 255 );
		TheDisplay->drawLine( pixelStart.x, pixelStart.y, pixelEnd.x, pixelEnd.y, 1.0f, colorStart, colorEnd );
	*/


	}

	// TheSuperHackers @info Flush the last batch if one is pending.
	flushParticleBatch(rinfo, pointCount);

		/// @todo lorenzen sez: this should be debug only:
	TheParticleSystemManager->setOnScreenParticleCount(m_onScreenParticleCount);

	//Draw any particles belonging to weather effects
	if (TheSnowManager)
		((W3DSnowManager *)TheSnowManager)->render(rinfo);

	//Now process screen smudges which are particles that distort the background behind them.
	if(TheSmudgeManager)
	{
		((W3DSmudgeManager *)TheSmudgeManager)->render(rinfo);
	}
}

Bool W3DParticleSystemManager::finishedBatch(const ParticleSystem& system, const RefCountPtr<TextureClass>& texture)
{
	return texture.Peek() != m_batchTexture.Peek() ||
		system.getShaderType() != m_batchShaderType ||
		system.getParticleAlignment() != m_batchParticleAlignment;
}

void W3DParticleSystemManager::initializeBatch(const ParticleSystem& system, const RefCountPtr<TextureClass>& texture)
{
	m_batchTexture = texture;
	m_batchShaderType = system.getShaderType();
	m_batchParticleAlignment = system.getParticleAlignment();
}

void W3DParticleSystemManager::flushParticleBatch(RenderInfoClass& rinfo, UnsignedInt& pointCount)
{
	if (pointCount > 0)
	{
		m_pointGroup->Set_Texture(m_batchTexture.Peek());

		switch (m_batchShaderType)
		{
		case ParticleSystemInfo::ADDITIVE:
			m_pointGroup->Set_Shader(ShaderClass::_PresetAdditiveSpriteShader);
			break;
		case ParticleSystemInfo::ALPHA:
			m_pointGroup->Set_Shader(ShaderClass::_PresetAlphaSpriteShader);
			break;
		case ParticleSystemInfo::ALPHA_TEST:
			m_pointGroup->Set_Shader(ShaderClass::_PresetATestSpriteShader);
			break;
		case ParticleSystemInfo::MULTIPLY:
			m_pointGroup->Set_Shader(ShaderClass::_PresetMultiplicativeSpriteShader);
			break;
		}

#ifdef __APPLE__
		if (m_batchParticleAlignment != ParticleSystemInfo::PARTICLE_ALIGNMENT_BILLBOARD && TheTerrainLogic != nullptr)
		{
			renderGroundBatch(rinfo, pointCount);
			pointCount = 0;
			m_batchTexture.Clear();
			m_batchParticleAlignment = ParticleSystemInfo::PARTICLE_ALIGNMENT_BILLBOARD;
			m_batchShaderType = ParticleSystemInfo::INVALID_SHADER;
			return;
		}
#endif

		m_pointGroup->Set_Flag(PointGroupClass::TRANSFORM, true);
		m_pointGroup->Set_Point_Mode(PointGroupClass::QUADS);
		m_pointGroup->Set_Arrays(m_posBuffer, m_RGBABuffer, nullptr, m_sizeBuffer, m_angleBuffer, nullptr, pointCount);
		m_pointGroup->Set_Billboard(m_batchParticleAlignment == ParticleSystemInfo::PARTICLE_ALIGNMENT_BILLBOARD);
		m_pointGroup->Set_Point_Frame(0);
		m_pointGroup->Render(rinfo);

		pointCount = 0;
	}

	m_batchTexture.Clear();
	m_batchParticleAlignment = ParticleSystemInfo::PARTICLE_ALIGNMENT_BILLBOARD;
	m_batchShaderType = ParticleSystemInfo::INVALID_SHADER;
}

#ifdef __APPLE__
//-------------------------------------------------------------------------------------------------
// TheSuperHackers @feature Particles that lie flat on the ground (radiation and toxin fields, shockwave
// rings, ground glows) are drawn as a grid that follows the terrain and the water surface, instead of a
// flat square that cuts into hills and floats over dips. Each particle keeps its height above the
// ground at its centre.
//-------------------------------------------------------------------------------------------------
static Real groundSurfaceHeight(Real x, Real y)
{
	Real waterZ = 0.0f;
	if (TheTerrainLogic->isUnderwater(x, y, &waterZ))
		return waterZ;
	return TheTerrainLogic->getGroundHeight(x, y);
}

static Int groundGridCells(Real halfSize)
{
	// About one cell per 6 world units; terrain cells are 10 units.
	Int cells = (Int)ceilf(2.0f * halfSize / 6.0f);
	return cells < 1 ? 1 : (cells > 16 ? 16 : cells);
}

void W3DParticleSystemManager::renderGroundBatch(RenderInfoClass& rinfo, UnsignedInt pointCount)
{
	const Vector3 *posArray = m_posBuffer->Get_Array();
	const Real *sizeArray = m_sizeBuffer->Get_Array();
	const Vector4 *colorArray = m_RGBABuffer->Get_Array();
	const uint8 *angleArray = m_angleBuffer->Get_Array();

	ShaderClass shader = ShaderClass::_PresetAlphaSpriteShader;
	switch (m_batchShaderType)
	{
	case ParticleSystemInfo::ADDITIVE: shader = ShaderClass::_PresetAdditiveSpriteShader; break;
	case ParticleSystemInfo::ALPHA: shader = ShaderClass::_PresetAlphaSpriteShader; break;
	case ParticleSystemInfo::ALPHA_TEST: shader = ShaderClass::_PresetATestSpriteShader; break;
	case ParticleSystemInfo::MULTIPLY: shader = ShaderClass::_PresetMultiplicativeSpriteShader; break;
	default: break;
	}
	shader.Set_Cull_Mode(ShaderClass::CULL_MODE_DISABLE);
	// The vertex colours carry each particle's colour and alpha, as in PointGroupClass::Render.
	shader.Set_Primary_Gradient(ShaderClass::GRADIENT_MODULATE);
	shader.Set_Texturing(m_batchTexture.Peek() ? ShaderClass::TEXTURING_ENABLE : ShaderClass::TEXTURING_DISABLE);

	Matrix3D view;
	rinfo.Camera.Get_View_Matrix(&view);
	DX8Wrapper::Set_Transform(D3DTS_WORLD, Matrix3D(true));
	DX8Wrapper::Set_Transform(D3DTS_VIEW, view);
	VertexMaterialClass *material = VertexMaterialClass::Get_Preset(VertexMaterialClass::PRELIT_DIFFUSE);
	DX8Wrapper::Set_Material(material);
	REF_PTR_RELEASE(material);
	DX8Wrapper::Set_Shader(shader);
	DX8Wrapper::Set_Texture(0, m_batchTexture.Peek());

	const Int maxVertices = 16384;
	UnsignedInt first = 0;
	while (first < pointCount)
	{
		// Particles that fit into one draw.
		Int vertexCount = 0, indexCount = 0;
		UnsignedInt last = first;
		while (last < pointCount)
		{
			const Int cells = groundGridCells(sizeArray[last]);
			const Int verts = (cells + 1) * (cells + 1);
			if (last > first && vertexCount + verts > maxVertices)
				break;
			vertexCount += verts;
			indexCount += cells * cells * 6;
			++last;
		}

		DynamicVBAccessClass vbAccess(BUFFER_TYPE_DYNAMIC_DX8, DX8_FVF_XYZNDUV2, vertexCount);
		DynamicIBAccessClass ibAccess(BUFFER_TYPE_DYNAMIC_DX8, indexCount);
		{
			DynamicVBAccessClass::WriteLockClass vbLock(&vbAccess);
			DynamicIBAccessClass::WriteLockClass ibLock(&ibAccess);
			VertexFormatXYZNDUV2 *vb = vbLock.Get_Formatted_Vertex_Array();
			unsigned short *ib = ibLock.Get_Index_Array();
			if (vb == nullptr || ib == nullptr)
				return;

			Int base = 0;
			for (UnsignedInt i = first; i < last; ++i)
			{
				const Vector3 &center = posArray[i];
				const Real halfSize = sizeArray[i];
				const Int cells = groundGridCells(halfSize);
				const Real angle = (Real)angleArray[i] / 255.0f * 2.0f * PI;
				const Real c = Cos(angle), s = Sin(angle);
				const unsigned diffuse = DX8Wrapper::Convert_Color_Clamp(colorArray[i]);
				// Height above the surface at the centre; a little more keeps the grid off the terrain,
				// whose triangles it does not match exactly.
				Real lift = center.Z - groundSurfaceHeight(center.X, center.Y);
				lift = (lift > 0.0f ? lift : 0.0f) + 0.75f;

				for (Int row = 0; row <= cells; ++row)
				{
					// Local coordinates run from 1 to -1, as PointGroupClass lays out ground aligned quads.
					const Real b = 1.0f - 2.0f * (Real)row / (Real)cells;
					for (Int col = 0; col <= cells; ++col)
					{
						const Real a = 1.0f - 2.0f * (Real)col / (Real)cells;
						const Real x = center.X + (a * c - b * s) * halfSize;
						const Real y = center.Y + (a * s + b * c) * halfSize;
						vb->x = x;
						vb->y = y;
						vb->z = groundSurfaceHeight(x, y) + lift;
						vb->nx = 0.0f;
						vb->ny = 0.0f;
						vb->nz = 1.0f;
						vb->diffuse = diffuse;
						vb->u1 = (1.0f - a) * 0.5f;
						vb->v1 = (1.0f - b) * 0.5f;
						vb->u2 = 0.0f;
						vb->v2 = 0.0f;
						++vb;
					}
				}
				for (Int row = 0; row < cells; ++row)
				{
					for (Int col = 0; col < cells; ++col)
					{
						const unsigned short v0 = (unsigned short)(base + row * (cells + 1) + col);
						const unsigned short v1 = (unsigned short)(v0 + 1);
						const unsigned short v2 = (unsigned short)(v0 + cells + 1);
						const unsigned short v3 = (unsigned short)(v2 + 1);
						*ib++ = v0; *ib++ = v2; *ib++ = v1;
						*ib++ = v1; *ib++ = v2; *ib++ = v3;
					}
				}
				base += (cells + 1) * (cells + 1);
			}
		}

		DX8Wrapper::Set_Vertex_Buffer(vbAccess);
		DX8Wrapper::Set_Index_Buffer(ibAccess, 0);
		DX8Wrapper::Draw_Triangles(0, indexCount / 3, 0, vertexCount);
		first = last;
	}

	DX8Wrapper::Set_Index_Buffer(nullptr, 0);
	DX8Wrapper::Set_Vertex_Buffer(nullptr);
}
#endif
