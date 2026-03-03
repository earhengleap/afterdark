import urllib.request, re

url = "https://bad.news/t/5986416"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    
    # Try different meta tag formats
    og1 = re.findall(r'<meta[^>]+property=[\'"]og:video[\'"][^>]+content=[\'"]([^\'"]+)[\'"]', html)
    og2 = re.findall(r'<meta[^>]+content=[\'"]([^\'"]+)[\'"][^>]+property=[\'"]og:video[\'"]', html)
    og3 = re.findall(r'og:video.*?content="([^"]+)"', html)
    
    print("OG Match 1:", og1)
    print("OG Match 2:", og2)
    print("OG Match 3:", og3)
    
    # Try finding html5 video tags inside the page
    video_srcs = re.findall(r'<video[^>]*>.*?<source[^>]+src=[\'"]([^\'"]+)[\'"]', html, re.DOTALL | re.IGNORECASE)
    print("Video tag sources:", video_srcs)
    
    # Try finding raw twimg mp4s
    twimgs = re.findall(r'https://video\.twimg\.com/[^\s"\'<>]+\.mp4', html)
    print("Total twimg MP4s found:", len(twimgs))
    if twimgs:
        print("First MP4:", twimgs[0])
        print("Last MP4:", twimgs[-1])
        
except Exception as e:
    print("Error:", e)
