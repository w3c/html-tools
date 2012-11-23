dummy:
	@echo "USAGE: make [html|2dcontext|microdata|all]"

all: html 2dcontext microdata
html: output/html/single-page.html
2dcontext: output/2dcontext/single-page.html
microdata: output/microdata/single-page.html

output/html/single-page.html: source
	python scripts/publish.py html
	cp -R images output/html/
	cp -R fonts output/html/
	cp 404/* output/html/

output/2dcontext/single-page.html: source
	python scripts/publish.py 2dcontext
	cp -R images output/2dcontext/
	cp -R fonts output/2dcontext/

output/microdata/single-page.html: source
	python scripts/publish.py microdata
	cp -R fonts output/microdata/
