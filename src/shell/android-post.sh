#!/usr/bin/env bash

if [ "x$TARGET_PRODUCT" == "x" ]; then
	echo "WARNING: Its recommended to launch from android build"
	echo "environment to take advantage of product/device-specific"
	echo "functionality."
fi

export PYTHONPATH=$LISA_HOME/../devlib:$PYTHONPATH
export PYTHONPATH=$LISA_HOME/../trappy:$PYTHONPATH
export PYTHONPATH=$LISA_HOME/../bart:$PYTHONPATH
