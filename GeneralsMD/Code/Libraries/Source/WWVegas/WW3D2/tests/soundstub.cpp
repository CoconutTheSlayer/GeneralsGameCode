// Stand-ins for the WWAudio sound definition referenced by the sound render
// object, which the WW3D integration test never uses.
#include "WWAudio/AudibleSound.h"

AudibleSoundDefinitionClass::AudibleSoundDefinitionClass() {}
uint32 AudibleSoundDefinitionClass::Get_Class_ID() const { return 0; }
const PersistFactoryClass& AudibleSoundDefinitionClass::Get_Factory() const { return *(const PersistFactoryClass*)nullptr; }
bool AudibleSoundDefinitionClass::Save(ChunkSaveClass&) { return false; }
bool AudibleSoundDefinitionClass::Load(ChunkLoadClass&) { return false; }
PersistClass* AudibleSoundDefinitionClass::Create() const { return nullptr; }
AudibleSoundClass* AudibleSoundDefinitionClass::Create_Sound(int) const { return nullptr; }
void AudibleSoundDefinitionClass::Initialize_From_Sound(AudibleSoundClass*) {}
LogicalSoundClass* AudibleSoundDefinitionClass::Create_Logical() { return nullptr; }
