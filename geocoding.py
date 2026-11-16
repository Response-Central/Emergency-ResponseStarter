"""Cached, serialized Nominatim address lookup for the small local app."""
import json
import os
import time
import threading
from contextlib import closing
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from psycopg2.extras import Json
from database import get_connection

_lock=threading.Lock()
_last_request=0.0

class GeocodeError(Exception): pass
class AddressChoice(GeocodeError):
    def __init__(self,candidates):
        super().__init__('Choose the matching address, then save again.')
        self.candidates=candidates


def search_address(query):
    global _last_request
    if not isinstance(query,str) or not 3<=len(query.strip())<=500:
        raise GeocodeError('Enter a complete street address and city (3–500 characters).')
    query=' '.join(query.split())
    key=query.casefold()
    # Serialize the low-volume service across Flask processes too, including cache checks.
    with _lock, closing(get_connection()) as conn, conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(72495112)')
            cur.execute("SELECT results FROM GeocodeCache WHERE query=%s AND created_at>NOW()-INTERVAL '30 days'",(key,))
            row=cur.fetchone()
            if row:return row[0]
            endpoint=os.getenv('GEOCODER_URL','https://nominatim.openstreetmap.org/search')
            url=endpoint+'?'+urlencode({'q':query,'format':'jsonv2','addressdetails':1,'limit':5})
            req=Request(url,headers={'User-Agent':os.getenv('GEOCODER_USER_AGENT','ResponseCentral/1.0 (local educational incident coordination app)'), 'Accept':'application/json'})
            try:
                time.sleep(max(0,1.1-(time.monotonic()-_last_request)))
                _last_request=time.monotonic()
                with urlopen(req,timeout=10) as response:
                    raw=json.loads(response.read(1024*512))
                if not isinstance(raw,list):raise ValueError()
                results=[]
                for place in raw:
                    lat,lon=float(place['lat']),float(place['lon'])
                    if not -90<=lat<=90 or not -180<=lon<=180:continue
                    # Area-only matches are too broad to dispatch to an incident.
                    if place.get('addresstype') in ('country','state','county','city','town','village','municipality','postcode'):
                        continue
                    results.append({'place_id':str(place['place_id']), 'display_name':place['display_name'], 'latitude':lat,'longitude':lon})
            except (HTTPError,URLError,TimeoutError,ValueError,KeyError,TypeError,OSError):
                raise GeocodeError('Address lookup is unavailable. Try again shortly; no location was changed.') from None
            finally:
                # Includes failures and makes cross-process requests at least one second apart.
                time.sleep(1.1)
            cur.execute('INSERT INTO GeocodeCache(query,results) VALUES (%s,%s) ON CONFLICT(query) DO UPDATE SET results=EXCLUDED.results,created_at=NOW()',(key,Json(results)))
            return results


def resolve_address(address,place_id=None):
    candidates=search_address(address)
    if not candidates:
        raise GeocodeError('No precise address found. Check the street number, city, region, and postal code in the reported address.')
    if place_id is not None:
        chosen=next((p for p in candidates if p['place_id']==str(place_id)),None)
        if chosen:return chosen
        raise GeocodeError('That location choice has expired. Look up the address again.')
    if len(candidates)>1:raise AddressChoice(candidates)
    return candidates[0]
