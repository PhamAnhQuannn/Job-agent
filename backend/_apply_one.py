import asyncio, logging, os
logging.basicConfig(level=logging.INFO)
# LIVE apply - not dry run
os.environ['DRY_RUN'] = 'false'

from automation.apply_bot import run_apply_batch

async def main():
    result = await run_apply_batch()
    print()
    print('=== RESULT ===')
    for k, v in result.items():
        print(f'  {k}: {v}')

asyncio.run(main())
