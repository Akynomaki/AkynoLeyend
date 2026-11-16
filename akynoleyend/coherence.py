"""Runtime revision needed by the filesystem ABI and early texel replay fixes."""

from . import __version__
from .errors import ProjectError

HOST_REVISION = "directory304-early-texels-regmap759-output849-v2"

# Exact r9 distribution, in Windows and POSIX path order.
R9_HOST_SOURCES = {
    "a7d8e808f449c7c7403eb0ea6dbbe147ab15f32ba59865525afe75856ee93ec6",
    "6a423c9d59fb21c9d4c3d8244d9c4370433f08c00b3574f93a68a9fdffb35433",
}

# Known generated-code/host ABIs. Maintenance updates compatible host objects in place.
# Include the old platform-dependent Path ordering (Windows and POSIX).
PREVIOUS_HOST_SOURCES = {
    "0.4.3-test.1": {
        "47ffe71f2ee66633a2430cd6274c8132abdf7361d21d3373c85ce1cf09a07721",
        "7d2b02f836049915084038c0a5318bb65454db7e4956f658c922c3e6842931ce",
    },
    "0.4.3-test.2": {
        "3b564d1259ca3ffe3c6e6e06247ae1ee9d3e55b2bab4b423af6fecb80aa8119f",
        "7075b5e051bbde188f035861d0331a4a6b668da5a4ab58fc36c9894574576736",
    },
    "0.4.3-test.3": {
        # Windows Test 3, verified from the installed game's manifest in T02.
        # No generated-code ABI or lift hook changes in the upstream candidate.
        "9b71fcc98444139a9c1388ca6d575ef5fa8cd1083693a450142e2a09b40c1e7a",
    },
    "0.4.3-test.4": {
        # Windows Test 4 as distributed (update package r3 and its standalone updater). The r4/r5 hotfix keeps the
        # version: it changes host/mkw_glue.c and the renderer only, no generated-code ABI or lift hook.
        "71f9c713c302a5957789df7b69061e7c36305c408cdae605aca80bb6e6cf7554",
        # r4 (this version, handed to testers for the Kokiri memory diagnosis; superseded by r5): the identity in
        # the manifest of a build updated with that package.
        "4dcab089e49a8daea96113fa15f4db91ff2f547828f76fdc6d5259f23903c865",
        # r5 (this version, the one testers have now): the identity in the manifest of a build updated with that
        # package. r6 changes host C files and Python only; the generated-code ABI and the lift hooks are the same.
        "8c8cc9634327bb4ce6a87d562edf871c204db62fd2af8e32f95918fbc0df9b01",
        # Windows r6: a correção da ordem dos locks altera apenas o host.
        "52cb1fffeaedccc35c7bb419eef4c4f17d561e482985b04d8ba6637b53046c3d",
        # r6 with the log and heap-race fixes and the FSR overlay, made with Criar (the three camera jitter hooks in the
        # generated code; host_features fsr-temporal-jitter-v1). Its work keeps those hooks, which the host still defines.
        "6d40619f36e1ce2858195ed101a75c43c7dca9cafff21c5f676965c4005fb71a",
        # The next build's first local update (write-back diff, DLSS engine): the same hooks and generated code.
        "934e48c76354c2e71876a3d0816efcd71d5b3b704069119cd699a9ca571f1e72",
        "28691a6a0df578640cf9ed43e439b27090bc344da300ce24b599c198c9bf93ee",
        # r7 with the exit fix (the GPU idle and NVIDIA DLSS shut down before the process ends): host and renderer only.
        "6170b0f3a8dd1e507a594a65cc6f2ed45c2852f9eb88c4214e0194b61d5a29e3",
        "e0be7dab93226140d3ca8c4d0e33333137dc767f2d4b1f7c5f4da2b67394b75c",
        # Exact r7 distribution, hashed in Windows and POSIX path order.
        "d767c496db943c7b31ff1f4bf1b563f4773eaf6e7484aa5fbc632eff18e850af",
        "02cf443e2ec470fe3965f3431e167c2f7ea5054283a0d1b149253283dcb3cead",
        # Exact r8 distribution. The Akyno F1 panel changes only renderer UI.
        "f835197895fdaca951ee6496eebb3b6a96280b4e37bbafd6c57f9eb63d71181c",
        "1de1cdf12410d71fd5b27009ff92cbfbdede13f49721ecec8ead2ae2de43547a",
        # r9 first pass: the F1 rows from Hookshot v2.1.0 and the frame-time step hook.
        "524396b1f93df16fc1433c8b446033a2ce1852d359949fa1c3e732c3a38a3332",
        *R9_HOST_SOURCES,
        # The r9 correction (AkynoLeyend-Correcao-r9.zip: outputs 1280x720 and 2560x1600, display.c and nn_applet.c), from the
        # manifest of the Windows build updated with it. r10 changes host C, the renderer and Python: the generated-code ABI
        # is the same, and its update adds the frame-step hook to a work that lacks it (nx2/upgrade_output.py).
        "96c4506f939f7123272c3cb57888b66252efa408fac8f329043a61669bb1d94c",
        # r10's first package (its step-hook update missed a CRLF file in that work): the same generated-code ABI.
        "2bc6a61383e9035d672d49eb2ebd20977d3ca3fd88adf44d331400b03ebe3981",
        # r10 as installed on Windows (the step hook added by the update): r11 changes the renderer, docs and tests only.
        "b9c4d38473f145a1427f4d56e8616473fba5bc980bdc97881e28cd6d80a3b9e4",
        # r12's first local pass (Hookshot v2.1.0's SDL host: controllers, motion; no generated-code change).
        "51a74f491721277cd3690449485fbd88ad9cd551b6d384f9ab72e5e69fe1db37",
        # r11 as installed on Windows (renderer only over r10's generated code).
        "f3cc4f8f2b940be66be64c147d9a21c2f14c96779948e130e9c83bf1592dbf55",
        # r12's last local pass, then r12 as installed on Windows (the SDL host, motion, the microphone; a64_stubs.c made again
        # by the lift's generator). r13 adds three hooks to the lifted code through nx2/upgrade_output.py (text speed and size,
        # mouse camera, camera centering): the generated-code ABI is the same.
        "e867f3565959cd139d7986c891dc12d1ca971cfcd96c8127a0385c0eb8e8ecae",
        "dc95a42d48a23bdd9dd74dc2709692526ebf53eb94bc0cace45abb28948b1b69",
        # r13's local passes (the panel hooks in the lifted code: text, mouse camera, centering, then ultrawide's three; host
        # and renderer after them, HDR among them). The generated-code ABI is the same.
        "dc44768a18ed28df028ccc68e9bdf9d8dfb39227e90511a715c3bbc54498e262",
        "4a51746373df731d085de0950033e2d533cda6931c5da32b33b4d40558a36223",
        "adc7ceb0bec7e1346c9dcc5924e57c13d812816b63ebce4bb05410b0fb58044d",
        "3eb38e75708be19da2ce56eb792b5ee571d36f108b852aaf2cc73ae0f0393868",
        "2c815532d951a3a311791e293fb974f1375b0a6a9f8f31ee52b346ab276e8031",
        "79b2c1bcbc95e2afc69729105f6656ec44e6e89d107672c91cd557599de587cd",
        # r13 as installed on Windows (text, mouse camera, HDR, ultrawide menus; the panel hooks added by the update). The mesh
        # shader compute fallback after it changes the renderer and Eden's back end on the fallback path only: same ABI.
        "9ff48a5b690e62f299ce7e25668b4d9ec3bdc1d01bbe3d151131b318f2dc8ce2",
        # The mesh fallback's local pass (renderer and Eden's SPIR-V back end; the stamp kept through the registry).
        "1f1548825fd0d0dfc1836b2bdf38fa0d84bf8a1a89837cc46cbcd027c728a027",
        # r13b (the mesh shader compute fallback) as installed on Windows and in the development build. r13c names the program
        # cache's files by mesh path and checks a package against the installed game while staging: same ABI.
        "5f544f6e9e53918356709f942dcbce03ca66d4a971e20d08ba94f2c7e6e56298",
        # r13c as distributed and installed on Windows (the manifest of the code-70 session's build; the same identity from the
        # r13c sources). r13d writes the renderer's last log lines before its own exits and names the caches by GPU: host C,
        # renderer and Python only, same ABI.
        "aeef577d4d5ce2ad470536c8ee47d676d5b3af67f6896919a24f9ac588a1b307",
        # r13d as distributed and installed on Windows (the Teste-1 install updated from r8 on 12/11/2026). r13e is the
        # renderer's VRAM control only: same ABI.
        "7f647493b97bb4a1ee7557da61b06a5e28ed50ae1220872c1b7fd4f7da2e4131",
        # r13e as installed on Windows (the same Teste-1 install, 12/11/2026). r13f lets Eden translate the point mesh
        # programs: renderer only, same ABI.
        "eb9fe478e0c3558e67ceddf26ba1315e138cd2d241bdcd6123f54335d92ee195",
        # r13f as installed on Windows (the same Teste-1 install, 12/11/2026). r13g finalizes images by texture object and
        # holds the VRAM pressure level: renderer only, same ABI.
        "08ae7037ab95ac9f45bed7e3397d70b908bcf012c1500320f682de9cc79b0944",
        # r13g as installed on Windows (the same Teste-1 install, 12/11/2026). r13h counts samples passed with occlusion
        # queries and turns the game's own occlusion on in the default mode: renderer and Python only, same ABI.
        "6cb74d1d609017de3a892b983c40de053bfef464f4e5137ecfd7f8df58577360",
        # r13h as installed on Windows (the same Teste-1 install, 12/11/2026). r13i changes host/hos_thread.c (the game's short
        # sleeps on the timer with six logical processors or fewer), Eden's task and mesh loads and the texture eviction target:
        # host C and renderer only, same ABI.
        "3cd96182fa2f0df1b4811203a7ea7279e3f08c2427f5015de3a5181415f7c463",
        # r13i's first package as installed on Windows (the same Teste-1 install, 12/11/2026; reported working by the player).
        # The final r13i package changes only this list and the notes: same ABI.
        "23bc5eab486fe309bdd66553e27f3ca6d679206793ba196a7873c25e6502c8a5",
        # The final r13i package (its sources, as a build updated with it records them). r13j chooses the x86-64 level by the
        # CPU (akynoleyend/cpu.py) and explains 0xC000001D: Python only, same ABI.
        "235ade6f68a0f8e49dffe8b1a29edf38aaf3d262c18a93c1622e3ee73a54b5ed",
        # r13j as distributed and installed on Windows (the Teste-1 install, 12/11/2026). 0.4.4 merges it with the Intel branch
        # below: renderer, Eden's back end behind flags off on NVIDIA, and Python; same ABI.
        "8851c0073d1ad831718b2c8c7e1ab900c160e71a36d1f57a2e2e4cc9e49a112e",
        # The Intel branch, parallel to r13d-r13j from r13c (aeef577d, above): its r13d (Hookshot v2.1.0's compare-exchange cap,
        # invariant positions and colour NaN guard for cards other than NVIDIA, the uniform snapshot on Intel) and r13e (storage
        # buffer ends on alignments over 16, the launcher's exit reasons). Same ABI.
        "b025ed01a81e211765cbe320ba0b1ae0b97904ceb32f916a5e3765c479cd57b9",
        "d86e20c0f217f22222a495bc886d7043db2d4b851fff3b60842d1c21c3a8d5c1",
        "eb3a85dd93a24ab8fe7bb6c0a98efbe93071b4ba715249d364db30886ca318e7",
        # The Intel branch's final r13e package (AkynoLeyend-Atualizacao-0.4.3-test.4-r13e.zip, SHA-256 7d9ab673...), from its
        # sources as a build updated with it records them.
        "734f9f2d3b911554293806ac762c8babf9e80b7d2abc93fa34b4fb1f56072d16",
        # The r13k/r13l branch (integrated GPU memory class, fine ASTC as RGBA8 there, native float atomic add), parallel to
        # 0.4.4/0.4.5 from r13j: renderer, Eden's back end and Python only. Same ABI and objects; the last is r13l as installed
        # on the Intel test installation (13/11/2026).
        "b56675f5f698ba12b8495332238c80b2cd79dc37df0e0fc3b0fe21952ff451c9",
        "950826518519f186a7442e33df60a1a98306501a26b206f088cf7b6e437a553a",
        "4d067faa92c033b4ad2d00a05133e11a2bc28481f7b5a1ee75b082e47a01e110",
        "5552f4ed6d892269aece5b47e7a9f11aa64de26b806fdb24c842f75e19f0a3a5",
        "f85167fb7e7d002b81463d1340c781e620eebc2913a934601682b4572e19b120",
        "4455961f1cacdd1e2e3cf97d7b7722516502cb1e9751171477b629534d726a50",
    },
    "0.4.4": {
        # 0.4.4's first package (the merge, before Ferramentas > EXPORTAR SAVES) as installed on Windows (the Teste-1 install,
        # 12/11/2026). EXPORTAR SAVES adds akynoleyend/saves.py and the launcher's button: Python and launcher only, same ABI.
        "34b170389e06c9cb1ffb21a08952527c9b80b0806b0998c06bc8899875523523",
        # 0.4.4's final package (with EXPORTAR SAVES), as installed on the Teste-1 (12/11/2026) and as the restored tree.
        # 0.4.5 changes the build's speed only (nx2/build.py, nx2/nup.py, akynoleyend/compile_plan.py): same ABI and objects.
        "6af0f4e0a1e41f123f54352789d75c327529b9653e4cab9d8b930160766b8771",
    },
    "0.4.5": {
        # 0.4.5 as distributed and installed on the Teste-1 (13/11/2026). 0.4.5-test.1 changes frame generation only
        # (gpu/vk: the dynamic count and the pacer, the F1 panel's rows) and the launcher's option: same ABI and objects.
        "87dc43b5829ff947c459b6f5ab493e86b522ea390cdb9a8e14bf9105be1e8ffd",
        "5f44dffa1a8a7e3a916f5497b04f8ddb17114e531bc6298abb82f436e88d9947",
    },
    "0.4.5-test.1": {
        # Exact original test.1 archive, hashed in Windows and POSIX path order.
        "e8a1da01e2f0e1be65e599551e06e3027cacf7190a9142c86efa689a60dc6b32",
        "ccedcffafc32bc7a0a023db9b1c4289a67068db7c803818dbb791135b574e515",
        # Exact prior renderer candidate, Windows and POSIX path order.
        "df76cd9ce03758f3382f2d8c92875eb4d7623808f53c77ed53357e18acf309ca",
        "cc6d1c1c3aed4dcb82913cfc1724b36246ef954d0e38e7c31ff82e7107d1d489",
        # Renderer candidate with fallback prewarm and native float atomics.
        "ca89a378bad51b7a2e23207ab0ec83ae98820cc3cd38a17289f2dbf22f0b7fc6",
        "dbd484a9430e8950f384dbbb4528a31a2936644fea8bf598e1db405953670b96",
        # The Render-VRAM candidate (2 MiB write-back shadows), Windows and POSIX path order. The unified candidate adds the
        # integrated GPU's memory class (r13k, r13l) and the render distance hook (nx2/upgrade_output.py, HOOKS_STAMP v3):
        # same ABI and objects but the one block the hook is in.
        "5b63a1d429ed4c81530a02df815551a4894b6197403708fee577e1d8c94fc605",
        "752e8e483f7d9a388d895b4e49b5f703803f80d60cbafee0ae74aa34a5c7844f",
        # (the unified candidate's development passes, akdev/s: same ABI)
        "acbf6f9ea1b6b42d3b409d45ecfb1d1513a59d1a51d507b7a6694f085ad63b2d",
        "16aeff05f2e945b26f80d01042637f9131ed86cc34ee86f07c959b1229dab10b",
        "bab0722513841b8fa112a7d3825119112f6f282c69e979e618cb9b3394cbf0ea",
        "fadc5f869dd35544936a4ff39ff752b1b4fda65a42185dd58dda551cb97e56b5",
        # The unified candidate as distributed (AkynoLeyend-Atualizacao-Unificada-0.4.5-test.1.zip, 14/11/2026), its source
        # tree in Windows and POSIX path order: what a build updated with it records.
        "4062b0cfd439f189cc9c9466c949f6347e1bb36f3dba13ab5b8ba1eb0c149e2b",
        "ee6953d70e0a23b28757595d46c0db46dbff8e4e410001670625da308142f159",
        # (0.4.7: the two branches from test.1 had a key each here; one dict key, both sets. Main line:) 0.4.5-test.1 as
        # installed on the Teste-1 (13/11/2026, its manifest; df76cd9c above), then the test.1 source tree (e8a1da01 above).
        # 0.4.5-test.2 changes host/nvn_native.c (the submit's replay without the virtual core) and host/mkw_glue.c (the
        # memory map every 30 s with HOS_MEM_MAP), Python and the launcher: same ABI, the game's objects kept.
    },
    "0.4.5-test.2": {
        # 0.4.5-test.2 as installed on the Teste-1 (13/11/2026, its manifest; the test.2 source tree gives the same). 0.4.5-test.3 changes
        # host/nvn_native.c (the core kept by default again), the renderer (two image pools), Python and the launcher: same
        # ABI, the game's objects kept.
        "081373776e2f4647d34dc88686a3814be8c860087fe15443b146a1b2a17007ed",
    },
    "0.4.5-test.3": {
        # 0.4.5-test.3 as installed on the Teste-1 (14/11/2026, its manifest). 0.4.5-test.4 changes host/mkw_glue.c (the
        # sampler: several threads, call chains), the renderer (render targets reused under VRAM pressure), Python and the
        # launcher: same ABI, the game's objects kept.
        "d168e3be355380fc3f5f8842bafdd9ea902cc60ce972967922c7fe40a2682bff",
    },
    "0.4.5-test.4": {
        # 0.4.5-test.4 as installed on the Teste-1 (14/11/2026, jogo/AkynoLeyend-build.json). 0.4.5-test.5 changes Python
        # (a measurement mode), tools/resumo_medicao.py and the launcher only: no host C, no renderer, the game's objects kept.
        "8c0c9073fec691692e9071da977e973ff4894bd5f14cc8dfae199c5b742f92d1",
    },
    "0.4.5-test.5": {
        # 0.4.5-test.5 as installed on the Teste-1 (14/11/2026, jogo/AkynoLeyend-build.json). 0.4.5-test.6 changes
        # host/hos_thread.c (the game's main thread's short sleeps yield instead of waiting on the timer), Python and the
        # launcher: same ABI, the game's objects kept.
        "d79a9a71f95d0d8458f912b52f3a6ec47c5f050da9e6c9a1d846edd9ecf7922e",
    },
    "0.4.5-test.6": {
        # 0.4.5-test.6 as installed on the Teste-1 (14/11/2026, jogo/AkynoLeyend-build.json). 0.4.5-test.7 changes
        # host/hos_thread.c (the main thread's short sleeps spin on the clock; a core waiter spins before it sleeps),
        # Python and the launcher: same ABI, the game's objects kept.
        "83a595c1a6f66d713db571ca19263d8c36c6b4fd4be10ac6264b407eafbbc530",
    },
    "0.4.5-test.7": {
        # 0.4.5-test.7 as installed on the Teste-1 (14/11/2026, jogo/AkynoLeyend-build.json). 0.4.5-test.8 changes
        # host/hos_thread.c (every short sleep spins by default; the Presentation Thread at the highest priority), Python
        # and the launcher: same ABI, the game's objects kept.
        "edf749fc3d818f2cc63fe6b6d83bb2d51f4e2666213ca51bb758add0c4f9588e",
    },
    "0.4.5-test.8": {
        # 0.4.5-test.8 as installed on the Teste-1 (14/11/2026, jogo/AkynoLeyend-build.json). 0.4.6 changes
        # host/hos_thread.c (the Presentation Thread's highest priority removed), Python and the launcher (no Teste de
        # desempenho): same ABI, the game's objects kept.
        "b7e6521ffb4b78b043c1401eb444dc82901890974d95310aa5176b71cd64de06",
    },
    "0.4.6": {
        # 0.4.6 as installed on the Teste-1 (14/11/2026, jogo/AkynoLeyend-build.json). 0.4.7 changes only the launcher's
        # look and texts and the version: same ABI, the game's objects kept.
        "01dd7fee3d40dc2feee1e74d81ee26c9ed6364d9b4ceab5d904ad0cc6ccb7ddb",
    },
    "0.4.7": {
        # 0.4.7 before the unified branch came in (the launcher's look), as installed on the Teste-1 (14/11/2026,
        # jogo/AkynoLeyend-build.json; its source tree gives the same in Windows order), then that tree in POSIX order.
        # The unified 0.4.7 adds the 0.4.5-test.1 unified branch (renderer, nx2 output and render distance hooks, host/nn_vi.c,
        # Python): same ABI, the game's objects kept but the blocks the hooks are in.
        "bc8ecd3c98c85da4be33ab8bbf1ba5af5e1b41731872f6f2c84c42839adfd8e9",
        "18d4b5bdef07a02be1d7bee15c7dee7492d531b7e15ba48fe31174fa6c6ac337",
        # (0.4.8) the unified 0.4.7 as its update installs it (AkynoLeyend-Atualizacao-0.4.7.zip, 14/11/2026: the copy of the
        # Teste-1 it was applied on), the same as its source tree in Windows order, then in POSIX order. 0.4.8 changes the
        # renderer (the start's preload), the launcher (its version) and Python: same ABI, the game's objects kept.
        "7661e6c99c842080c46e0bbc56119109cbdee925b26c6651174fa9654b706f65",
        "b3c7d8cb699380bcc49c55668fe9f7cf93217b8c0d485ab067e25bd73faa32ff",
    },
    "0.4.8": {
        # Original Windows package and the two Vulkan performance updates use the same generated host.
        "47c4982f115f741d470c06162e01070a57fda94d19385684322bf4b154d39f70",
        "d2795b59e0d15f57515d8f65d5d69e11ad89a405124b7c9ffddd76ae25482b73",
        "c56b011b501eb87f56b4a1cf6d26c8290d13cc3eb190ac725b9c8f86c559a90d",
        # (0.4.9) the final 0.4.8 source tree (the performance update included, commit 334c75b), what its complete package's
        # Criar records. 0.4.9 changes the renderer (the decorative vegetation and effects option, the draw stats' columns),
        # Python and the launcher: no host C, same ABI, the game's objects kept.
        "bc0d21660a20abcc6746d257c24f73ba7d73adf8bfdac683af64f3493bed6913",
    },
}


def compatible_previous_host(manifest):
    if not isinstance(manifest.get("version"), str) or not isinstance(manifest.get("source_sha256"), str):
        return False
    return (manifest.get("host_revision") == HOST_REVISION
            and manifest.get("source_sha256") in PREVIOUS_HOST_SOURCES.get(manifest.get("version"), ())
            and str(manifest.get("game_build_id", "")).startswith("e0f3ccfa"))


def require_host(manifest):
    current = manifest.get("version") == __version__ and manifest.get("host_revision") == HOST_REVISION
    if not current and not compatible_previous_host(manifest):
        raise ProjectError(
            "Este build nao corresponde ao host/ABI desta revisao. Use Criar ou "
            "Compilar.cmd com sua entrada original e aguarde @@done. "
            "Trocar apenas a DLL nao aplica a correcao de diretorios/texturas iniciais."
        )
