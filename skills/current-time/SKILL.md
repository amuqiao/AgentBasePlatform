---
name: Current Time Query
description: This skill provides the ability to query the current date and time using Python code.
---

# Current Time Query

## Overview

When the user asks about the current date, time, or timestamp, use this skill to provide accurate information.

## Usage

Run the following Python code to get the current time:

```python
from datetime import datetime
now = datetime.now()
print(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Date: {now.strftime('%Y-%m-%d')}")
print(f"Time: {now.strftime('%H:%M:%S')}")
print(f"Weekday: {now.strftime('%A')}")
```
