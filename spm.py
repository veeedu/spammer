# play_fullscreen.py
import time
import sys

# Try to set Windows master volume to 100%
def set_volume_100_windows():
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        # 1.0 == 100%
        volume.SetMasterVolumeLevelScalar(1.0, None)
        return True
    except Exception as e:
        print("Warning: couldn't set system volume (not Windows or dependency missing).", e)
        return False

# Play a video URL/fullpath in fullscreen using python-vlc and wait until done
def play_video_fullscreen(video_path_or_url):
    try:
        import vlc
    except Exception as e:
        print("python-vlc is not installed or couldn't be imported:", e)
        return False

    try:
        # Create instance and media player
        instance = vlc.Instance()
        player = instance.media_player_new()
        media = instance.media_new(video_path_or_url)
        player.set_media(media)

        # Start playback
        player.play()
        # Give it a moment to start
        time.sleep(0.2)

        # Try to set full screen (may depend on VLC/libvlc availability)
        try:
            player.set_fullscreen(True)
        except Exception:
            pass

        # Wait until playback ends (or error)
        state = player.get_state()
        while state not in (vlc.State.Ended, vlc.State.Error):
            time.sleep(0.5)
            state = player.get_state()

        # Stop and release
        player.stop()
        return state == vlc.State.Ended
    except Exception as e:
        print("Error while playing video:", e)
        return False

def main():
    # Replace with the raw URL to the mp4 on GitHub (raw link)
    video_url = "https://raw.githubusercontent.com/veeedu/fundraising/main/rickroll.mp4"

    print("Setting volume to 100% (Windows)...")
    set_volume_100_windows()

    print("Playing video full screen. This will block until playback finishes...")
    ok = play_video_fullscreen(video_url)
    if ok:
        print("Playback finished normally.")
    else:
        print("Playback ended with error or was interrupted.")

if __name__ == "__main__":
    main()
