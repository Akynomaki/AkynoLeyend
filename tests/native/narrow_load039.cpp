#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
using u32=uint32_t;using u64=uint64_t;using Id=uint64_t;
#define LOG_WARNING(...) ((void)0)
struct EmitContext {
    struct { bool support_int64=true; } profile;
    Id U32[2]{0,0}, U64=0, load_global_func_u32=0;
    std::array<uint8_t,256> bytes{};
    Id Const(u32 x) { return x; }
    Id Constant(Id,u64 x) { return x; }
    Id OpBitwiseAnd(Id,Id x,Id y) { return x&y; }
    Id OpUConvert(Id,Id x) { return uint32_t(x); }
    Id OpShiftLeftLogical(Id,Id x,Id y) { return uint32_t(x)<<y; }
    Id OpFunctionCall(Id,Id,Id address) {
        assert(!(address&3));
        u32 word=0;std::memcpy(&word,bytes.data()+(address&255),4);return word;
    }
    Id OpBitFieldUExtract(Id,Id word,Id shift,Id n) {
        return (uint32_t(word)>>shift)&((1u<<n)-1);
    }
    Id OpBitFieldSExtract(Id,Id word,Id shift,Id n) {
        const u32 x=uint32_t(OpBitFieldUExtract(0,word,shift,n));
        return uint32_t(int32_t(x<<(32-n))>>(32-n));
    }
};
// ACTUAL_NARROW_EMITTERS
int main() {
    EmitContext ctx;
    for (unsigned k=0;k<100;k++) {
        for (unsigned i=0;i<256;i++)ctx.bytes[i]=uint8_t(i*71+k*113);
        for (unsigned i=0;i<256;i++) {
            const u64 address=0x1000000000ull+i;
            assert(EmitLoadGlobalU8(ctx,address)==ctx.bytes[i]);
            assert(EmitLoadGlobalS8(ctx,address)==u32(int32_t(int8_t(ctx.bytes[i]))));
            if (!(i&1)) {
                uint16_t x;std::memcpy(&x,ctx.bytes.data()+i,2);
                assert(EmitLoadGlobalU16(ctx,address)==x);
                assert(EmitLoadGlobalS16(ctx,address)==u32(int32_t(int16_t(x))));
            }
        }
    }
    ctx.profile.support_int64=false;
    assert(EmitLoadGlobalU8(ctx,0)==0 && EmitLoadGlobalS16(ctx,0)==0);
}
