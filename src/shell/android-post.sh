#!/usr/bin/env bash

if [ "x$TARGET_PRODUCT" == "x" ]; then
	echo "WARNING: Its recommended to launch from android build"
	echo "environment to take advantage of product/device-specific"
	echo "functionality."
else
	lisadir="$(gettop)/$(get_build_var BOARD_LISA_TARGET_SCRIPTS)"

	if [ -d $lisadir/targetdev ]; then
		export PYTHONPATH=$lisadir:$PYTHONPATH
		echo "Welcome to LISA $TARGET_PRODUCT environment"
		echo "Target-specific scripts are located in $lisadir"

		monsoon_path="$ANDROID_BUILD_TOP/cts/tools/utils/"
		export PATH="$monsoon_path:$PATH"
		echo "Monsoon will run from: $monsoon_path"
	else
		echo "LISA scripts don't exist for $TARGET_PRODUCT, skipping"
	fi
fi

export PYTHONPATH=$LISA_HOME/../devlib:$PYTHONPATH
export PYTHONPATH=$LISA_HOME/../trappy:$PYTHONPATH
export PYTHONPATH=$LISA_HOME/../bart:$PYTHONPATH
