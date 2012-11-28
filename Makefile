PATH=../html

dummy:
	@echo "USAGE: make [html|2dcontext|microdata|all]"

all: html 2dcontext microdata
html: $(PATH)/output/html/single-page.html
2dcontext: $(PATH)/output/2dcontext/single-page.html
microdata: $(PATH)/output/microdata/single-page.html

$(PATH)/output/html/single-page.html: $(PATH)/source
	python publish.py html

$(PATH)/output/2dcontext/single-page.html: $(PATH)/source
	python publish.py 2dcontext

$(PATH)/output/microdata/single-page.html: $(PATH)/source
	python publish.py microdata
