app_name=$(notdir $(CURDIR))
build_tools_directory=$(CURDIR)/build/tools
source_build_directory=$(CURDIR)/build/artifacts/source
source_package_name=$(source_build_directory)/$(app_name)
appstore_build_directory=$(CURDIR)/build/artifacts/appstore
appstore_package_name=$(appstore_build_directory)/$(app_name)
npm=$(shell which npm 2> /dev/null)
version=$(shell grep \<version\> appinfo/info.xml|cut -f2 -d\>|cut -f1 -d\<)

all: build

.PHONY: build
build: build-dep check
	npm run build
	npm run buildviewer

# Removes the appstore build
.PHONY: clean
clean:
	rm -rf ./js ./css
	rm -rf ./dist

# Builds the source and appstore package
.PHONY: dist
dist: build
	rm -rf ./js ./css
	cp -r dist/js js
	cp -r dist/css css
	make appstore

# Builds the source package for the app store, ignores php and js tests
.PHONY: appstore
appstore:
	rm -rf $(appstore_build_directory)
	mkdir -p $(appstore_build_directory)
	tar cvzf $(appstore_package_name)_$(version).tar.gz \
	--exclude-vcs \
	--exclude="../$(app_name)/dist" \
	--exclude="../$(app_name)/tests" \
	--exclude="../$(app_name)/Makefile" \
	--exclude="../$(app_name)/*.log" \
	--exclude="../$(app_name)/phpunit*xml" \
	--exclude="../$(app_name)/composer.*" \
	--exclude="../$(app_name)/node_modules" \
	--exclude="../$(app_name)/build" \
	--exclude="../$(app_name)/old" \
	--exclude="../$(app_name)/js/tests" \
	--exclude="../$(app_name)/js/*.log" \
	--exclude="../$(app_name)/js/bower.json" \
	--exclude="../$(app_name)/js/karma.*" \
	--exclude="../$(app_name)/package.json" \
	--exclude="../$(app_name)/package-lock.json" \
	--exclude="../$(app_name)/bower.json" \
	--exclude="../$(app_name)/karma.*" \
	--exclude="../$(app_name)/protractor\.*" \
	--exclude="../$(app_name)/.*" \
	--exclude="../$(app_name)/js/.*" \
	--exclude="../$(app_name)/webpack.js" \
	--exclude="../$(app_name)/stylelint.config.js" \
	--exclude="../$(app_name)/vue.config.js" \
	--exclude="../$(app_name)/src" \
	--exclude="../$(app_name)/lib/bin/__pycache__" \
	../$(app_name)

.PHONY: fixcode
fixcode:
	.tools/coding-standard/vendor/bin/php-cs-fixer fix lib -vv

# Installs npm dependencies
.PHONY: build-dep
build-dep:
	npm install

.PHONY: check
check:
	npm run lint

.PHONY: check-fix
check-fix:
	npm run lint:fix
