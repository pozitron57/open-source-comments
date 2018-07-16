layout: osc
title: Open-source self-hosted comments
fixedheader: false
description: A table of comparison of open-source self-hosted comments
comments: true
---

<script src="data.js"></script>

<div class="preamble">

# Open-source self-hosted comments for static websites

Inspired by [staticsitegenerators.net](http://staticsitegenerators.net). 
Contribute at [github](https://github.com/pozitron57/open-source-comments).

Want different columns?
[Propose](https://github.com/pozitron57/open-source-comments/issues/new).

## What's wrong with Disqus

Disqus loads absurd amount of tracking services, which compromises
your visitors personal data and significantly increases loading time.
See, e.g., [this
post](http://donw.io/post/github-comments/#what-s-wrong-with-disqus).

## What's not covered here

For a static website, one usually wants a lightweight commenting server with
as little dependencies as possible. Few commenting engines listed on the page
are provided by heavy frameworks and web-applications (e.g.,
[django-fluent-comments](https://github.com/django-fluent/django-fluent-comments),
[discourse](https://github.com/discourse/discourse),
[talkyard](https://github.com/debiki/talkyard)), but the majority are relatively
lightweight applications designed specifically to provide comments for the
static pages.

This page prioritizes info on *self-hosted* comments. However,
there are other solutions, including implementations of third-party services 
(e.g., Github issues, such as
[[1]](https://github.com/imsun/gitment),
[[2]](https://github.com/gitalk/gitalk),
[[3]](https://github.com/Blankj/awesome-comment),
[[4]](https://github.com/utterance/utterances)).

## Choose columns to show
</div>

<table id="results" class="display" style="width:100%"></table>

<script>
$(document).ready(function() {
  $('#results').DataTable({
    //LengthChange: true,
    //LengthMenu: [ [10, 25, -1], [10, 25, "Все"] ],
    //pageLength: 12,
    paging:false,
    data:osc_data,
    columns:cols,
    order:[[0,"desc"]],
    searchHighlight: true,
    info:true,
    scrollX:true,
    //fixedHeader: { header: true },
    //scrollCollapse:true, // what's that?
    //fixedColumns:{leftColumns:2},
    dom: 'Bfrtip',
    buttons: [ 
        {extend: 'columnsToggle'},
        {extend: 'colvisGroup', text: 'Show all columns', show: ':hidden'},
        'colvisRestore'],
    columnDefs: [
        {targets: "_all",
            className: 'dt-center'},
        { "visible": false,  
          "targets": [
      3,6,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36]},
        ],
    //stateSave:true,
    searching:true,
  });
});
</script>
