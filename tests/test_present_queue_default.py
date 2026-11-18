"""The presents on a queue of a compute family of their own by default with NVIDIA's driver 621.24 and newer on Windows
(RX_VK_PRESENT_QUEUE).

On the replay's queue a present waits behind the game's next frame, so frame generation's frames, each presented at its own
time, reached the screen together: with V-Sync Off at 3x a third of them under 2 ms after the one before (an RTX 5090 on
621.24), 0.1% or less on a queue of their own. v2.0.9 turned the queue off for Hookshot issue 1161 (an RTX 4090 on NVIDIA's
621.14 had a black screen with it on, 4e24bd4d); that fault was never placed, so older NVIDIA drivers, other drivers and
Linux stay off.

The text checks (gpu/vk/vk_main.cpp create_device): on Windows the default is NVIDIA's proprietary driver from 621.24 on,
off elsewhere; the RX_VK_PRESENT_QUEUE switch comes after it, by the switches' yes/no rule, and decides either way; the
compute family is looked for only when wanted, and only a compute family without graphics. The device-lost message names
the switch while the queue is in use, and DLSS Frame Gen's exit wait bounds the queues' own locks too (a present on the
presents' queue lets dev.present_mu go). docs/development.md and gpu/vk/switches.def have the switch's row with its default.

    python -I -B tests/test_present_queue_default.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import between  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    main_cpp = (ROOT / "gpu" / "vk" / "vk_main.cpp").read_text(encoding="utf-8")
    choice = between(main_cpp, "uint32_t compute_family = UINT32_MAX;", "// (hookshot) The presenter thread's own queue",
                     where="gpu/vk/vk_main.cpp create_device")
    win = between(choice, "#ifdef _WIN32", "#endif", where="create_device's queue choice")
    assert "bool want = false;" in choice, "create_device: off where nothing says otherwise (other drivers, Linux)"
    assert "constexpr uint32_t kPresentQueueNvidia = (621u << 22) | (24u << 14);" in win and \
        "want = dp.driverID == VK_DRIVER_ID_NVIDIA_PROPRIETARY && dev.props.driverVersion >= kPresentQueueNvidia;" in win, \
        "create_device: on by default with NVIDIA's driver 621.24 and newer on Windows (621.14: Hookshot issue 1161)"
    assert (621 << 22 | 14 << 14) < (621 << 22 | 24 << 14) <= (621 << 22 | 24 << 14) < (622 << 22), "NVIDIA's version order"
    env = 'if (const char* e = getenv("RX_VK_PRESENT_QUEUE"); e && *e) want = !env_value_off(e);'
    assert env in choice and choice.index("#endif") < choice.index(env), \
        "create_device: RX_VK_PRESENT_QUEUE decides after the default, either way"
    assert re.search(r"for \(uint32_t i = 0; want && i < n && compute_family == UINT32_MAX; i\+\+\)\s*"
                     r"if \(\(families\[i\]\.queueFlags & VK_QUEUE_COMPUTE_BIT\) && "
                     r"!\(families\[i\]\.queueFlags & VK_QUEUE_GRAPHICS_BIT\)\)", choice), \
        "create_device: a compute family without graphics, only when wanted"
    dev = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    row = [l for l in dev.splitlines() if l.startswith("| `RX_VK_PRESENT_QUEUE=0` or `1` |")]
    assert len(row) == 1 and "the default with NVIDIA's driver 621.24 and newer on Windows" in row[0], \
        "docs/development.md: the RX_VK_PRESENT_QUEUE row and its default"
    sw = (ROOT / "gpu" / "vk" / "switches.def").read_text(encoding="utf-8")
    assert "SW(RX_VK_PRESENT_QUEUE, hw, bool, \"on with NVIDIA's driver 621.24 and newer on Windows" in sw, \
        "gpu/vk/switches.def: the switch follows the PC's driver (hw), on with NVIDIA's on Windows"
    replay = (ROOT / "gpu" / "vk" / "vk_replay.cpp").read_text(encoding="utf-8")
    lost = between(replay, "[[noreturn]] void device_lost(const char* why) {", "\n}\n", where="gpu/vk/vk_replay.cpp")
    assert "dev.present_queue_supported ?" in lost and "RX_VK_PRESENT_QUEUE=0" in lost and "replay_fatal(lost);" in lost, \
        "device_lost: the way back named while the presents are on their own queue"
    dlss = (ROOT / "gpu" / "vk" / "vk_dlss.cpp").read_text(encoding="utf-8")
    close = between(dlss, "void dlss_fg_close() {\n    // (not only where it is asked for now", "\n}\n", where="gpu/vk/vk_dlss.cpp")
    assert "!free_by_then(dev.present_queue_mu) || !free_by_then(dev.presenter_queue_mu)" in close and \
        close.index("free_by_then(dev.present_queue_mu)") < close.index("device_wait_idle_locked();"), \
        "dlss_fg_close: the presents' own queues free before the idle wait, within the exit's 2 s"
    print("PASS: the presents on their own compute queue by default with NVIDIA's driver 621.24 and newer on Windows")


if __name__ == "__main__":
    main()
