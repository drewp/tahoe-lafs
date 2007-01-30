
default: build

BASE=$(shell pwd)

.PHONY: build
build: build-pyfec build-Crypto
	python setup.py install --prefix=$(BASE)/instdir

build-pyfec:
	cd src/pyfec && python ./setup.py install --prefix=$(BASE)/instdir

build-Crypto:
	cd src/Crypto && python ./setup.py install --prefix=$(BASE)/instdir

INSTDIR=$(PWD)/instdir/lib/python$(shell python -c 'import sys;print sys.version_info[0]').$(shell python -c 'import sys;print sys.version_info[1]')/site-packages

ifneq ($(PYTHONPATH),)
PP=PYTHONPATH=${PYTHONPATH}:$(INSTDIR)
else
PP=PYTHONPATH=$(INSTDIR)
endif

.PHONY: run-queen run-client test

run-queen:
	cd queen-basedir && PYTHONPATH=.. twistd -noy ../queen.tac

run-client: build
	cd client-basedir && $(PP) twistd -noy ../client.tac

run-client2:
	cd client-basedir2 && PYTHONPATH=.. twistd -noy ../client.tac
run-client3:
	cd client-basedir3 && PYTHONPATH=.. twistd -noy ../client.tac


TEST=allmydata
REPORTER=

# use 'make test REPORTER=--reporter=bwverbose' from buildbot, to supress the
# ansi color sequences
test: build
	$(PP) trial $(REPORTER) $(TEST)

test-figleaf: build
	rm -f .figleaf
	$(PP) trial --reporter=bwverbose-figleaf $(TEST)

figleaf-output:
	$(PP) python misc/figleaf2html -d coverage-html -r `python ./builddir.py`
	@echo "now point your browser at coverage-html/index.html"
# after doing test-figleaf and figleaf-output, point your browser at
# coverage-html/index.html

.figleaf.el: .figleaf
	$(PP) python misc/figleaf2el.py .figleaf `python ./builddir.py`

pyflakes:
	pyflakes src/allmydata

count-lines:
	@echo -n "lines: "
	@cat `find src -name '*.py'` |wc --lines
	@echo -n "TODO: "
	@grep TODO `find src -name '*.py'` | wc --lines

clean:
	rm -rf build
	rm -f debian

create_dirs:
	mkdir -p queen-basedir
	mkdir -p client-basedir
	mkdir -p client-basedir2
	mkdir -p client-basedir/storage
	mkdir -p client-basedir2/storage

DEBVER=`head -1 debian/changelog | sed -e 's/^[^(]*(\([^)]*\)).*$$/\1/' | sed -e 's/^\([0-9]\+\.[0-9]\+\.[0-9]\+\).*$$/\1/'`
DEBSTRING=$(DEBVER)-T`date +%s`
DEBCOMMENTS="'make deb' build"

show:
	echo $(DEBVER)
	echo $(DEBSTRING)

.PHONY: setup-dapper setup-sid deb-dapper deb-sid increment-deb-version
.PHONY: deb-dapper-head deb-sid-head

setup-dapper:
	rm -f debian
	ln -s dapper/debian debian
	chmod a+x debian/rules

setup-sid:
	rm -f debian
	ln -s sid/debian debian
	chmod a+x debian/rules


deb-dapper: setup-dapper
	fakeroot debian/rules binary
deb-sid: setup-sid
	fakeroot debian/rules binary

increment-deb-version:
	debchange --newversion $(DEBSTRING) $(DEBCOMMENTS)
deb-dapper-head: setup-dapper increment-deb-version
	fakeroot debian/rules binary
deb-sid-head: setup-sid increment-deb-version
	fakeroot debian/rules binary
