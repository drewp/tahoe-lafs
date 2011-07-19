$(function () {
    function displayStats(data) {
	$("#started").text(new Date(data.started * 1000).toString());
	$("#si").text(data.storage_index);
	$("#helper").text(data.helper ? "Yes" : "No");
	$("#total_size").text(data.total_size);
	$("#progress").text(data.progress * 100);
	$("#status").text(data.status);
    }

    function displayPopups(jq) {
	/*
	within the elements in jq, whenever the mouse is within one of
	those, clone its .popup child and follow the mouse with that
	clone.
	*/
	var currentPopup, popupIsFor;
	jq.mousemove(function (ev) {
	    if (ev.target != popupIsFor) {
		if (currentPopup) {
		    currentPopup.remove();
		}
		currentPopup = $(this).find(".popup").clone();
		currentPopup.show();
		$("body").append(currentPopup);
		popupIsFor = ev.target;
	    }
	    currentPopup.css({left: ev.pageX + 10, top: ev.pageY - 15});
	}).mouseleave(function (ev) {
	    if (ev.target == popupIsFor) {
		currentPopup.remove();
		popupIsFor = null;
	    }
	});
    }

    function onDataReceived(data) {
	displayStats(data);
	
	var pxPerSec = 200;
	function xForTime(t) { return (t - data.started) * pxPerSec; }
	function dxForTime(dt) { return dt * pxPerSec; }

	function timelineBar(event) {
	    var sx = xForTime(event.start_time), ex = xForTime(event.finish_time);
	    var ret = $("<div>").addClass("timelineBar").css({
		marginLeft: sx+"px", 
		width: (ex - sx) + "px"});
	    return ret;
	}
	function barPost(event) {
	    return $("<div>").addClass("timelinePost").css("left", xForTime(event.finish_time));
	}
	function makeRow(cls) {
	    var r = {
		elem: $("<div>"),
		row: $("<div>").addClass("event "+cls),
		labelCol: $("<div>").addClass("label"),
		valueCol: $("<div>").addClass("value"),
		timingCol: $("<div>").addClass("timing")
	    }
	    r.row.append(r.labelCol).append(r.valueCol).append(r.timingCol);
	    r.elem.append(r.row);

	    return r;
	}
	function makeExpandChild(row) {
	    var child = $("<div>").addClass("child").hide();
	    row.elem.append(child);
	    row.row.prepend($("<div>").addClass("expander").text("+"));
	    row.row.click(function () { 
		child.toggle(); 
		row.row.find(".expander").text(child.is(":visible") ? "-" : "+"); 
	    });
	    return child;
	}

	function makePopup(js) {
	    ret = $("<div>").addClass("popup").hide();
	    var expansions = {'shnum' : 'share number'}
	    for (k in js) {
		ret.append($("<div>").text((k in expansions ? expansions[k] : k)+": "+JSON.stringify(js[k])));
	    }
	    return ret;
	}

	var eventsDiv = $("#events");

	var eventRows = []; // [sortkey1, sortkey2, sortkey3, elem]

	function formatMs(seconds) {
	    return (Math.round(seconds * 100000) / 100) + "ms";
	}
	function formatPct(frac) {
	    return (Math.round(frac * 1000) / 10) + "%";
	}


	$.each(data.read, function (i, ev) {
	    var row = makeRow("read");
	    
	    row.labelCol.text("read() request");
	    row.timingCol.append(timelineBar(ev).text(ev.bytes_returned + " bytes"))
		.append(makePopup(ev));
	    
	    var elapsed = ev.finish_time - ev.start_time;
	    makeExpandChild(row)
		.append($("<div>").text(
		    "Read request for bytes "+ev.start+" to "+(ev.start+ev.length)+" ("+ev.length+" bytes)"))
		.append($("<div>").text(
		    "Elapsed time was "+formatMs(elapsed)+". "))
		.append($("<div>").addClass("indent").text(
		    formatMs(ev.decrypt_time)+" ("+formatPct(ev.decrypt_time / elapsed)+") spent on decryption"))
		.append($("<div>").addClass("indent").text(
		    formatMs(ev.paused_time)+" ("+formatPct(ev.paused_time / elapsed)+") spent paused."))

	    eventRows.push([ev.start_time, 0, 0, row]);
	});

	$.each(data.dyhb, function (i, ev) {
	    var row = makeRow("dyhb");

	    var post = barPost(ev).text("share numbers "+(ev.response_shnums.join(" ")))

	    row.labelCol.text("DYHB request");
	    row.valueCol.text(ev.serverid);
            row.timingCol.append(timelineBar(ev).text(ev.success ? "ok" : "fail"))
	       .append(post)
	       .append(makePopup(ev));

	    eventRows.push([ev.start_time, 0, 0, row]);
	});

	var segmentStarts = []; // [start_byte, segment_start_time]
	$.each(data.segment, function (i, ev) {
	    var row = makeRow("segment");

	    segmentStarts.push([ev.segment_start, ev.start_time]);

	    row.labelCol.text("segment() request");
	    row.valueCol.text("start="+ev.segment_start);
     	    row.timingCol.append(timelineBar(ev).text(ev.success ? "ok" : "fail"))
		.append(makePopup(ev));
	    
	    eventRows.push([ev.start_time, 0, 0, row]);
	});

	segmentStarts.sort();

	$.each(data.block, function (i, ev) {
	    var row = makeRow("block");

	    var duration = Math.round((ev.finish_time - ev.start_time) * 1000) + "ms"
	    
	    var mySegmentStarted;
	    $.each(segmentStarts, function (i, ss) {
		if (ss[0] <= ev.start) {
		    mySegmentStarted = ss[1];
		}
	    });

	    row.labelCol.text("block() request").css("padding-left","19px");
	    row.valueCol.text(ev.serverid);
	    row.timingCol.append(timelineBar(ev))
		.append(barPost(ev).text(duration + ev.start))
		.append(makePopup(ev));
//	    mySegmentStarted = ev.start_time;
	    eventRows.push([mySegmentStarted, ev.start, ev.start_time, row]);
	});

	eventRows.sort(function (a,b) {
	    return (a[0] == b[0] ? (a[1] == b[1] ? (a[2] == b[2] ? (1) : 
                   (a[2] - b[2])) : (a[1] - b[1])) : (a[0] - b[0]));
	});
	$.each(eventRows, function (i,r) {
	    eventsDiv.append(r[3].elem);
	});
	displayPopups($(".timing"));
    }
    $.ajax({url: "event_json",
            method: 'GET',
            dataType: 'json',
            success: onDataReceived });
});