import os
import sys
import time
import platform
import subprocess

# Helpful helper so the app can access files bundled by PyInstaller
def resource_path(relative_path):
    # When running as a onefile bundle, PyInstaller extracts files to _MEIPASS
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)

def set_volume_100_windows():
    try:
        # Use comtypes/pycaw approach for robust volume setting (requires pycaw)
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(1.0, None)  # 1.0 = 100%
    except Exception as e:
        # fallback: try PowerShell keypress approach (less reliable)
        try:
            subprocess.run(
                'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]175 * 50)"',
                shell=True,
                check=False
            )
        except Exception:
            print("Unable to set system volume automatically:", e)

def play_video_fullscreen(video_path):
    # Try python-vlc first (recommended) — requires VLC installed on the build machine / target or libvlc bundled
    try:
        import vlc
        instance = vlc.Instance()
        player = instance.media_player_new()
        media = instance.media_new(video_path)
        player.set_media(media)
        player.play()
        time.sleep(0.3)
        try:
            player.set_fullscreen(True)
        except Exception:
            pass
        state = player.get_state()
        while state not in (vlc.State.Ended, vlc.State.Error):
            time.sleep(0.5)
            state = player.get_state()
        player.stop()
        return True
    except Exception as e:
        # Fallback: try to call an external player (vlc.exe or mpv) on PATH
        for exe in ("vlc", "mpv", "wmplayer"):
            try:
                subprocess.run([exe, "--fullscreen", "--play-and-exit", video_path], check=True)
                return True
            except FileNotFoundError:
                continue
            except Exception:
                # try different flags or just open
                try:
                    if exe == "wmplayer":
                        subprocess.run(["start", video_path], shell=True)
                        return True
                    continue
                except Exception:
                    continue
        print("No suitable player found. Install VLC or MPV, or run this script with a player available.")
        return False

def main():
    # bundled video filename
    video_file = resource_path("rickroll.mp4")
    if not os.path.exists(video_file):
        print("Missing rickroll.mp4 in same folder as the script.")
        return

    if platform.system() == "Windows":
        set_volume_100_windows()
    else:
        # On Linux/Mac, try simple commands (optional)
        if platform.system() == "Linux":
            try:
                subprocess.run(["amixer", "sset", "Master", "100%"], check=False)
            except Exception:
                pass
        elif platform.system() == "Darwin":
            try:
                subprocess.run(["osascript", "-e", "set volume output volume 100"], check=False)
            except Exception:
                pass

    print("Playing video now...")
    ok = play_video_fullscreen(video_file)
    if ok:
        print("Playback finished.")
    else:
        print("Playback failed or was aborted.")

if __name__ == "__main__":
    main()
