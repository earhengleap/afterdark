import asyncio
from core.porn91_service import Porn91Service

async def test():
    paths, t, info = await Porn91Service.download_media("https://91porn.com/view_video.php?viewkey=be8ab11701ba6b5c95c4&page=2&c=pikt1&viewtype=basic&category=rf", 123)
    print("Paths:", paths)
    print("Info:", info)

asyncio.run(test())
