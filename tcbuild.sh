#!/bin/bash

# File to check
FILE='.build_id'

# Pattern to match
PATTERN="[0-9]+\.[0-9]+\.[0-9]+'"

# Check if the file content matches the pattern
if grep -qE "$PATTERN" "$FILE"; then
    echo "The content of the file matches the version pattern."
else
    echo "The content of the file does not match the version pattern."
    cat $FILE
fi