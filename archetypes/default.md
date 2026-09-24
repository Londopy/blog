---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
date: {{ .Date }}
draft: true
description: ""
tags: []
cover:
  image: "cover.png"
  alt: ""
  relative: true  # og:image / twitter:image resolve inside the page bundle
---
