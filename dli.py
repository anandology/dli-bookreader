"""Web app to display DLI books in Internet Archive book reader.
"""
import urllib2
import os
import web
import json
from bs4 import BeautifulSoup

urls = (
    "/", "index",
    "/(\d+)", "book",
    "/(\d+)\.json", "book_json",
    "/(\d+)/(\d+).jpg", "book_image",
)
app = web.application(urls, globals())

db = web.database(dbn="sqlite", db="dli.db")
render = web.template.render("templates/", globals={"json_encode": json.dumps})

IMGDIR = "cache"
METADATA_URL = "http://www.new.dli.ernet.in/cgi-bin/DBscripts/allmetainfo.cgi?barcode=%s"
IMAGE_URL = "http://www.new1.dli.ernet.in%(dirpath)s/PTIFF/%(index)08d.tif"

def get_book_metadata(barcode):
    rows = db.select("metadata", where="barcode=$barcode", vars=locals()).list()
    if rows:
        return json.loads(rows[0].metadata)
    else:
        d = _get_book_metadata(barcode)
        db.insert("metadata", barcode=barcode, metadata=json.dumps(d))
        return d

def _get_book_metadata(barcode):
    url = METADATA_URL % barcode
    data = urllib2.urlopen(url).read()
    soup = BeautifulSoup(data)
    tds = soup.find_all("td")
    d = dict((e1.get_text().strip(), e2.get_text().strip()) for e1, e2 in web.group(tds, 2))
    a = soup.find("a")
    read_url = a['href']
    d['read_url'] = read_url
    d['read_url_params'] = dict(kv.strip().split("=") for kv in read_url.split("?")[-1].split("&"))
    
    d['TotalPages'] = int(d['TotalPages'])
    d['SourceURL'] = url
    return d

class index:
    def GET(self):
        i = web.input()
        if "barcode" in i:
            raise web.seeother("/" + i.barcode)
        return render.index()

class book:
    def GET(self, barcode):
        book = get_book_metadata(barcode)
        return render.book(book)

class book_json:
    def GET(self, barcode):
        d = get_book_metadata(barcode)
        web.header("content-type", "application/json")
        return json.dumps(d)

class book_image:
    def GET(self, barcode, index):
        index = int(index)
        d = get_book_metadata(barcode)

        dirpath = d['read_url_params']['path1']
        url = IMAGE_URL % locals()
        tif_path = self.get_path(barcode, index, "tif")
        self.download(url, tif_path)

        jpg_path = self.get_path(barcode, index, "jpg")
        self.convert(tif_path, jpg_path)

        web.header("content-type", "image/jpeg")
        return open(jpg_path).read()

    def download(self, url, img_path):
        if os.path.exists(img_path):
            return
        
        print >> web.debug, "downloading", url
        data = urllib2.urlopen(url).read()
        with open(img_path, "wb") as f:
            f.write(data)
    
    def convert(self, tif, jpg):
        if os.path.exists(jpg):
            return
        cmd = "convert %s %s" % (tif, jpg)
        print >> web.debug, cmd
        os.system(cmd)

    def get_path(self, barcode, index, ext):
        filename = "%s-%08d.%s" % (barcode, int(index), ext)
        return os.path.join(IMGDIR, filename)
        
if __name__ == "__main__":
    app.run()
