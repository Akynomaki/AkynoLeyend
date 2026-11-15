"""Source rectangles shared by present, FSR and interpolation stay inside the texture."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PresentCropTests(unittest.TestCase):
    def test_intersections_and_signed_boundaries(self):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        source = r'''
#include <cassert>
#include <climits>
#include "present_crop.h"
using namespace mkwvk;
int main() {
    PresentCrop r;
    auto check = [&](int x, int y, int w, int h, int rx, int ry, unsigned rw, unsigned rh) {
        int crop[]{x,y,w,h};
        assert(present_crop(80,48,crop,r));
        assert(r.x==rx && r.y==ry && r.width==rw && r.height==rh);
    };
    check(7,4,48,32,7,4,48,32);
    check(-3,4,12,7,0,4,9,7);
    check(70,45,99,99,70,45,10,3);
    check(-5,-3,100,100,0,0,80,48);
    check(0,0,INT_MAX,INT_MAX,0,0,80,48);
    check(70,45,INT_MAX,INT_MAX,70,45,10,3);
    check(999,999,0,1,0,0,80,48); // existing convention: no positive crop means full texture
    assert(present_crop(80,48,nullptr,r) && r.width==80 && r.height==48);
    const int invalid[][4]={{80,0,1,1},{0,48,1,1},{-20,0,10,10},{0,-20,10,10},
                            {INT_MAX,INT_MAX,INT_MAX,INT_MAX},{INT_MIN,0,INT_MAX,1}};
    for(auto& crop:invalid) {
        r={1,1,1,1}; assert(!present_crop(80,48,crop,r));
        assert(r.x==0 && r.y==0 && r.width==0 && r.height==0);
    }
    assert(!present_crop(0,48,nullptr,r));
    assert(!present_crop(80,0,nullptr,r));
    assert(!present_crop(UINT_MAX,48,nullptr,r));
    assert(!present_crop(80,UINT_MAX,nullptr,r));
    assert(present_crop(INT_MAX,INT_MAX,nullptr,r));
    auto fitted = fit_present({0,0,3840,2160},2560,1600);
    assert(fitted.x==0 && fitted.y==80 && fitted.width==2560 && fitted.height==1440);
    fitted = fit_present({0,0,2560,1600},2560,1600);
    assert(fitted.x==0 && fitted.y==0 && fitted.width==2560 && fitted.height==1600);
    fitted = fit_present({0,0,2560,1600},1280,720);
    assert(fitted.x==64 && fitted.y==0 && fitted.width==1152 && fitted.height==720);
    fitted = fit_present({0,0,1920,1080},1280,720);
    assert(fitted.x==0 && fitted.y==0 && fitted.width==1280 && fitted.height==720);
    assert(!fit_present({},1280,720).width && !fit_present(r,0,720).width);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "crop.cpp").write_text(source)
            binary = path / "crop"
            built = subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                                    "-I" + str(ROOT / "gpu/vk"), str(path / "crop.cpp"), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
