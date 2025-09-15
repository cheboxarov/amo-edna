from fastapi import APIRouter, HTTPException, Query, Response
import httpx

router = APIRouter(prefix="/media")


@router.get("/proxy")
async def proxy_media(url: str = Query(..., description="Absolute URL to fetch")):
	try:
		async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
			resp = await client.get(url)
			resp.raise_for_status()
			content_type = resp.headers.get("Content-Type", "application/octet-stream")
			return Response(content=resp.content, media_type=content_type)
	except httpx.HTTPError as e:
		raise HTTPException(status_code=502, detail=f"Failed to fetch media: {str(e)}")

