from .client import KurentoClient
#
# import asyncio
# import time
#
#
# def write(msg):
#     print(msg, flush=True)
#
#
# async def say1():
#     await asyncio.sleep(1)
#     write("Hello 1!")
#
#
# async def say2():
#     await asyncio.sleep(1)
#     write("Hello 2!")
#
#
# write("start")
#
# async def main():
#     # Schedule three calls *concurrently*:
#     await asyncio.gather(say1(), say2())
# # create and close loop
# asyncio.run(main())
# print(asyncio.get_event_loop_policy())
# write("exit")

# loop.close()
"""
import asyncio
from concurrent.futures import ProcessPoolExecutor

print('running async test')

async def say_boo():
    i = 0

    while True:
        await asyncio.sleep(1)
        print('...boo {0}'.format(i))
        i += 1


async def say_baa():
    i = 0
    while True:
        await asyncio.sleep(1)
        print('...baa aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa{0}'.format(i))
        i += 1

if __name__ == "__main__":
    # async def main():
        loop = asyncio.get_event_loop()
        tasks = [
            asyncio.ensure_future(say_boo()),
            asyncio.ensure_future(say_baa()),
        ]
        # await asyncio.wait(tasks)
        asyncio.gather(*tasks)
        loop.run_forever()

    # asyncio.run(main())

"""
