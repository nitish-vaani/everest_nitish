import asyncio

async def book_an_appointment(contact_number:str, location: str):
    await asyncio.sleep(10)
    return "success"
