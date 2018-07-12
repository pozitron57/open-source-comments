layout: osc
title: Open-source comments
description: A table of comparison of open-source self-hosted comments
comments: true
---

<script src="data.js"></script>

<div class="preamble">

# Open-source self-hosted commenting systems

Inspired by [staticsitegenerators.net](http://staticsitegenerators.net). 
Contribute at [github](https://github.com/pozitron57/open-source-comments).

Want more columns? [Propose](https://github.com/pozitron57/open-source-comments/issues/new).

### Choose columns to show
</div>

<table id="results" class="display" style="width:100%"></table>

<script>
$(document).ready(function() {
  $('#results').DataTable({
    data:osc_data,
    columns:cols,
    order:[[0,"desc"]],
    searchHighlight: true,
    paging:false,
    info:false,
    scrollX:true,
    //fixedHeader: { header: true },
    //scrollCollapse:true,
    //fixedColumns:{leftColumns:2},
    dom: 'Bfrtip',
    buttons: [ 
      {extend: 'columnsToggle'},
      {extend: 'colvisGroup', text: 'Show all', show: ':hidden'},
      'colvisRestore'],
    columnDefs: [
        {targets: "_all",
            className: 'dt-center'},
        { "visible": false,  
          "targets": [ 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33 ] },
        ],
    //stateSave:true,
    searching:true,
  });
});
</script>
