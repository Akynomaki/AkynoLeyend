// (hookshot) The device's element order of the 16x8x16 f16 cooperative matrices HMMA_nx2 runs on.
//
// A lane's HMMA fragment registers hold its matrix elements in the console's order (PTX mma.m16n8k16's: two f16
// a register, low half first). The host's cooperative matrices hold each lane's share in an order of the
// implementation's own; vk_coopmat.cpp measures it at start, and only when every lane holds the same positions in
// both does the back end turn HMMA_nx2 on. Element e of the console's fragment is then the device's element
// mma_order_x[e].
#pragma once

#include <array>
#include <cstdint>

namespace Shader::Backend::SPIRV {

inline std::array<uint32_t, 8> mma_order_a{0, 1, 2, 3, 4, 5, 6, 7};
inline std::array<uint32_t, 4> mma_order_b{0, 1, 2, 3};
inline std::array<uint32_t, 4> mma_order_c{0, 1, 2, 3};
inline bool mma_software = false;   // (HMMA_nx2 in software: emit_spirv_warp.cpp, RX_VK_MMA_SOFTWARE=1)
// (amd-fix, from Hookshot v2.1.0; AkynoLeyend r13d: these three for every card but NVIDIA, set by vk_coopmat.cpp coopmat_init,
// so an NVIDIA card's SPIR-V is what it was) float colour outputs carry no NaN or infinity to their target (EmitSetFragColor):
// one NaN texel spreads through bloom/blur/downsample averages into glowing blocks (Hookshot issue 606). RX_VK_NO_NAN_GUARD=1 off.
inline bool frag_nan_guard = false;
// (amd-fix) gl_Position decorated Invariant (vertex and mesh outputs): the game draws a depth pre-pass, then the colour
// pass again with depth EQUAL; Maxwell computes the same position in both, other compilers may not without Invariant, and
// the colour pass is then rejected in spots. RX_VK_NO_INVARIANT=1 off. From NX2navi patch 0007.
inline bool position_invariant = false;
// (Hookshot issue 17) compare-exchange loops leave after CAS_LOOP_MAX_TRIES attempts (spirv_emit_context.cpp): a word out of
// bounds under robust buffer access never compares equal, and Intel's driver lost the device on that dispatch (the 275HX's
// integrated GPU, exit 70). RX_VK_NO_CAS_CAP=1 off.
inline bool cas_loop_cap = false;
// (AkynoLeyend r13e) a storage buffer's end in the search by address (spirv_emit_context.cpp define_body) from the address as
// given, not rounded down to the card's alignment: rounded, its last bytes went to the page table (0 where it maps nothing).
// Set when the card's minStorageBufferOffsetAlignment is over 16 (64 on Intel's integrated GPU). RX_VK_SSBO_END_ALIGNED=1 off.
inline bool ssbo_end_unaligned = false;
// (AkynoLeyend r13l) a float added atomically to a storage buffer word with the device's own atomic (OpAtomicFAddEXT,
// VK_EXT_shader_atomic_float shaderBufferFloat32AtomicAdd), not a compare-exchange loop: Intel's integrated GPU (275HX) lost the
// device in 499dbfd0721d2858, a 32 x 32 reduction whose warps all add into the same few words, and with the loop capped at
// CAS_LOOP_MAX_TRIES an addition can be dropped. Set off NVIDIA where the feature is (vk_coopmat.cpp). RX_VK_NO_FLOAT_ATOMIC_ADD=1 off.
inline bool float_atomic_add_native = false;

} // namespace Shader::Backend::SPIRV
