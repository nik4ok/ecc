# SPDX-License-Identifier: Apache-2.0
# Builds libwg-go.so (AmneziaWG 3 / IpcSet with header_protection_key).
# Requires: ANDROID_NDK_HOME, go 1.25+, clang from NDK.

ANDROID_PACKAGE_NAME ?= com.vpn.app
JNI_LIBS ?= $(CURDIR)/../../app/src/main/jniLibs
API_LEVEL ?= 24

HOST_TAG := $(shell uname -s | tr '[:upper:]' '[:lower:]')-$(shell uname -m | sed 's/arm64/aarch64/')
ifeq ($(HOST_TAG),darwin-aarch64)
  HOST_TAG := darwin-x86_64
endif
TOOLCHAIN := $(ANDROID_NDK_HOME)/toolchains/llvm/prebuilt/$(HOST_TAG)

.PHONY: all arm64-v8a armeabi-v7a clean

all: arm64-v8a armeabi-v7a

arm64-v8a:
	$(MAKE) abi ABI=arm64-v8a TRIPLE=aarch64-linux-android GOARCH=arm64

armeabi-v7a:
	$(MAKE) abi ABI=armeabi-v7a TRIPLE=armv7a-linux-androideabi GOARCH=arm GOARM=7

abi:
	@test -n "$(ANDROID_NDK_HOME)" || (echo "ANDROID_NDK_HOME is not set" && exit 1)
	mkdir -p "$(JNI_LIBS)/$(ABI)"
	CGO_ENABLED=1 GOOS=android GOARCH=$(GOARCH) $(if $(GOARM),GOARM=$(GOARM),) \
	CC="$(TOOLCHAIN)/bin/$(TRIPLE)$(API_LEVEL)-clang" \
	CGO_CFLAGS="--target=$(TRIPLE)$(API_LEVEL) --sysroot=$(TOOLCHAIN)/sysroot" \
	CGO_LDFLAGS="--target=$(TRIPLE)$(API_LEVEL) --sysroot=$(TOOLCHAIN)/sysroot -llog -Wl,-soname=libwg-go.so" \
	go build -tags linux \
	  -ldflags="-X github.com/amnezia-vpn/amneziawg-go/v3/ipc.socketDirectory=/data/data/$(ANDROID_PACKAGE_NAME)/cache/amneziawg -buildid=" \
	  -trimpath -buildvcs=false -buildmode c-shared \
	  -o "$(JNI_LIBS)/$(ABI)/libwg-go.so" .
	rm -f "$(JNI_LIBS)/$(ABI)/libwg-go.h"

clean:
	rm -rf "$(JNI_LIBS)"
