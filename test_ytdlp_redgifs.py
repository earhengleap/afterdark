import yt_dlp
def test():
    ydl_opts = {'quiet': False, 'no_warnings': False}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info("https://www.redgifs.com/watch/bowedsleepynandine", download=False)
            print("YT-DLP Success!", info.get('url')[:50])
        except Exception as e:
            print("YT-DLP Failed:", e)

test()
