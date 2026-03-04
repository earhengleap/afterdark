import asyncio
from core.porna91_service import Porna91Service

async def test():
    paths, t, info = await Porna91Service.download_media("https://91porna.com/comic/index/detail?video_key=283079", 999)
    print("Paths:", paths)
    print("Type:", t)
    print("Info:", info)

if __name__ == "__main__":
    asyncio.run(test())
