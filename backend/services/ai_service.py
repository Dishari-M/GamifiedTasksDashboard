async def enrich_task(title, description):
    if "bug" in title.lower():
        return {"difficulty":"hard","estimated":120,"impact":9}
    return {"difficulty":"medium","estimated":60,"impact":5}
