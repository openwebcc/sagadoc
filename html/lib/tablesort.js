/*****
*
* simple table sort
*
*****/

window.addEventListener("load", function () {
    var Sortable, tables, i, rows, cols, n;

    // the tool that does the work
    Sortable = function () { }
    Sortable.prototype.init = function (table) {
        var lastHeader, rows;

        // remember last header clicked for detecting reverse sort ...
        lastHeader = null;

        // activate sorting when the user clicks on header cells
        rows = table.getElementsByTagName("tr");
        rows.item(0).onclick = function (evt) {
            if (evt.target.nodeName === 'TR') {
                // do nothing if the user clicks on borders of the row
                return;
            }
            var sortObj, i, j, n, key_parts, key_comp;
            sortObj = {
                header : rows.item(0).childNodes,
                keys : [],
                vals : {}
            }
            for (i = 0; i < sortObj.header.length; i += 1) {
                if (evt.target === sortObj.header.item(i)) {
                    // set sort direction for this column
                    if (evt.target.hasAttribute("class")) {
                        lastSorted = evt.target.getAttribute("class");
                        evt.target.setAttribute("class", (lastSorted === 'sorted-asc') ? 'sorted-desc' : 'sorted-asc');
                    } else {
                        evt.target.setAttribute("class", 'sorted-asc');
                    }

                    // sort remaining rows
                    for (j = 1; j < rows.length; j += 1) {
                        // loop through columns of row, define a compound key and its values
                        cols = rows.item(j).childNodes;
                        key_parts = [];
                        for (n = 0; n < cols.length; n += 1) {
                            if (n !== i) {
                                // add column to the end
                                key_parts.push(cols.item(n).innerHTML);
                            } else {
                                // add it to the beginning (that makes it sort)
                                key_parts.unshift(cols.item(n).innerHTML);
                            }
                        }
                        // add unique identifier to the key parts
                        key_parts.push(j);

                        // join key parts and strip HTML tags
                        key_comp = key_parts.join(" ").replace(/<[^>]+>/g,"")

                        // remember keys and values
                        sortObj.keys.push(key_comp);
                        sortObj.vals[key_comp] = '<tr>' + rows.item(j).innerHTML + '</tr>';
                    }
                } else {
                    // reset sort direction for remaining columns
                    sortObj.header.item(i).removeAttribute("class");
                }
            }

            // sort list of compound keys ASC or DESC
            if (evt.target.hasAttribute("class")) {
                if (evt.target.getAttribute("class") === 'sorted-asc') {
                    sortObj.keys.sort();
                } else {
                    sortObj.keys.sort().reverse();
                }
            } else {
                sortObj.keys.sort();
            }

            // update remaining rows with sorted content
            for (i = 1; i < rows.length; i += 1) {
                rows.item(i).innerHTML = sortObj.vals[sortObj.keys[i - 1]];
            }
        };
    };

    // see if we have any sortable tables
    tables = document.getElementsByTagName("table");
    for (i = 0; i < tables.length; i += 1) {
        if (tables.item(i).getAttribute("class") === 'sortable') {
            s = new Sortable();
            s.init(tables.item(i));
        }
    }
}, false);
