from __future__ import annotations
from dataclasses import dataclass
from .media_library import ProductMediaLibrary,MediaAsset


@dataclass(frozen=True,slots=True)
class MediaResponse:
    asset:MediaAsset|None; reason:str; requires_employee:bool=False


class MediaSalesResponder:
    def __init__(self,library:ProductMediaLibrary): self.library=library
    def choose(self,product_id:str,request:str)->MediaResponse:
        q=request.lower()
        aliases={"بالليل":"night","ليل":"night","فيديو":"video","تصوير":"footage","دليل":"manual","كتالوج":"manual"}
        query=" ".join([q,*[v for k,v in aliases.items() if k in q]])
        hits=self.library.search(product_id,query)
        if not hits: return MediaResponse(None,"No verified matching product media",True)
        verified=[x for x in hits if x.verified]
        if not verified: return MediaResponse(None,"Matching media is not verified",True)
        return MediaResponse(verified[0],"Verified product media selected")
