﻿

/* timeplot-view.js */
Exhibit.TimeplotView=function(C,B){this._div=C;
this._uiContext=B;
this._settings={};
this._accessors={getLabel:function(F,E,D){D(E.getObject(F,"label"));
},getProxy:function(F,E,D){D(F);
},getColorKey:null};
this._legend=[];
this._largestSize=0;
var A=this;
this._listener={onItemsChanged:function(){A._reconstruct();
}};
B.getCollection().addListener(this._listener);
};
Exhibit.TimeplotView._settingSpecs={"timeplotConstructor":{type:"function",defaultValue:null},"timeGeometry":{type:"function",defaultValue:null},"valueGeometry":{type:"function",defaultValue:null},"timeplotHeight":{type:"int",defaultValue:400},"gridColor":{type:"text",defaultValue:"#000000"},"colorCoder":{type:"text",defaultValue:null},"showHeader":{type:"boolean",defaultValue:true},"showSummary":{type:"boolean",defaultValue:true},"showFooter":{type:"boolean",defaultValue:true}};
Exhibit.TimeplotView._accessorSpecs=[{accessorName:"getProxy",attributeName:"proxy"},{accessorName:"getTime",attributeName:"pointTime",type:"date"},{accessorName:"getValue",attributeName:"pointValue",type:"float"},{accessorName:"getSeriesConnector",attributeName:"seriesConnector",type:"text"},{accessorName:"getSeriesTime",attributeName:"seriesTime",type:"text"},{accessorName:"getSeriesValue",attributeName:"seriesValue",type:"text"},{accessorName:"getColorKey",attributeName:"colorKey",type:"text"},{accessorName:"getEventLabel",attributeName:"eventLabel",type:"text"}];
Exhibit.TimeplotView.create=function(D,C,B){var A=new Exhibit.TimeplotView(C,Exhibit.UIContext.create(D,B));
Exhibit.TimeplotView._configure(A,D);
A._internalValidate();
A._initializeUI();
return A;
};
Exhibit.TimeplotView.createFromDOM=function(D,C,B){var E=Exhibit.getConfigurationFromDOM(D);
var A=new Exhibit.TimeplotView(C!=null?C:D,Exhibit.UIContext.createFromDOM(D,B));
Exhibit.SettingsUtilities.createAccessorsFromDOM(D,Exhibit.TimeplotView._accessorSpecs,A._accessors);
Exhibit.SettingsUtilities.collectSettingsFromDOM(D,Exhibit.TimeplotView._settingSpecs,A._settings);
Exhibit.TimeplotView._configure(A,E);
A._internalValidate();
A._initializeUI();
return A;
};
Exhibit.TimeplotView._configure=function(A,C){Exhibit.SettingsUtilities.createAccessors(C,Exhibit.TimeplotView._accessorSpecs,A._accessors);
Exhibit.SettingsUtilities.collectSettings(C,Exhibit.TimeplotView._settingSpecs,A._settings);
var B=A._accessors;
A._getTime=function(F,E,D){B.getProxy(F,E,function(G){B.getTime(G,E,D);
});
};
};
Exhibit.TimeplotView.prototype.dispose=function(){this._uiContext.getCollection().removeListener(this._listener);
this._timeplot=null;
this._toolboxWidget.dispose();
this._toolboxWidget=null;
this._dom.dispose();
this._dom=null;
this._div.innerHTML="";
this._div=null;
this._uiContext.dispose();
this._uiContext=null;
};
Exhibit.TimeplotView.prototype._internalValidate=function(){if("getColorKey" in this._accessors){if("colorCoder" in this._settings){this._colorCoder=this._uiContext.getExhibit().getComponent(this._settings.colorCoder);
}if(this._colorCoder==null){this._colorCoder=new Exhibit.DefaultColorCoder(this._uiContext);
}}};
Exhibit.TimeplotView.prototype._initializeUI=function(){var A=this;
var B={};
B.colorGradient=(this._colorCoder!=null&&"_gradientPoints" in this._colorCoder);
this._div.innerHTML="";
this._dom=Exhibit.ViewUtilities.constructPlottingViewDom(this._div,this._uiContext,this._settings.showSummary&&this._settings.showHeader,{onResize:function(){A._timeplot.repaint();
}},B);
this._toolboxWidget=Exhibit.ToolboxWidget.createFromDOM(this._div,this._div,this._uiContext);
this._eventSources=[];
this._eventSource=new Timeplot.DefaultEventSource();
this._columnSources=[];
this._reconstruct();
};
Exhibit.TimeplotView.prototype._reconstructTimeplot=function(A){var D=this._settings;
if(this._timeplot!=null){this._timeplot.dispose();
this._timeplot=null;
}if(A){this._eventSource.addMany(A);
}var Q=this._dom.plotContainer;
if(D.timeplotConstructor!=null){this._timeplot=D.timeplotConstructor(Q,this._eventSource);
}else{Q.style.height=D.timeplotHeight+"px";
Q.className="exhibit-timeplotView-timeplot";
Q.id="timeplot-"+Math.floor(Math.random()*1000);
var H=(this._accessors.getColorKey!=null);
var B={mixed:false,missing:false,others:false,keys:new Exhibit.Set()};
var N=new Timeplot.Color(D.gridColor);
var J=D.timeGeometry(N);
var L=D.valueGeometry(N);
var C=[];
for(var K=0;
K<this._legend.length;
K++){var G=null;
if(H){var M=new Exhibit.Set();
M.add(this._legend[K]);
G=this._colorCoder.translateSet(M,B);
}this._columnSources.push(new Timeplot.ColumnSource(this._eventSource,K+1));
C.push(Timeplot.createPlotInfo({id:this._legend[K],dataSource:this._columnSources[K],timeGeometry:J,valueGeometry:L,lineColor:new Timeplot.Color(G),dotColor:new Timeplot.Color(G),showValues:true,roundValues:false}));
}this._timeplot=Timeplot.create(Q,C);
setTimeout(this._timeplot.paint,100);
if(H){var I=this._dom.legendWidget;
var F=this._colorCoder;
var P=B.keys.toArray().sort();
if(this._colorCoder._gradientPoints!=null){I.addGradient(this._colorCoder._gradientPoints);
}else{for(var E=0;
E<P.length;
E++){var O=P[E];
var G=F.translate(O);
I.addEntry(G,O);
}}if(B.others){I.addEntry(F.getOthersColor(),F.getOthersLabel());
}if(B.mixed){I.addEntry(F.getMixedColor(),F.getMixedLabel());
}if(B.missing){I.addEntry(F.getMissingColor(),F.getMissingLabel());
}}}};
Exhibit.TimeplotView.prototype._reconstruct=function(){var O=this;
var N=this._uiContext.getCollection();
var L=this._uiContext.getDatabase();
var V=this._settings;
var W=this._accessors;
var C=N.countRestrictedItems();
var P=[];
this._dom.legendWidget.clear();
for(var S=0;
S<this._columnSources.length;
S++){this._columnSources[S].dispose();
}this._columnSources=[];
this._eventSource.clear();
this._eventSource=new Timeplot.DefaultEventSource();
if(C>0){var F=N.getRestrictedItems();
var B=[];
var U={};
var H=new SimileAjax.Set([]);
var K=new SimileAjax.Set([]);
var A=function(Y){var f;
W.getSeriesTime(Y,L,function(e){f=e;
return true;
});
var Z;
W.getSeriesValue(Y,L,function(e){Z=e;
return true;
});
var a;
W.getLabel(Y,L,function(e){a=e;
return true;
});
var j=f.split(";");
var d=Z.split(";");
if(j.length!=d.length){throw"Exhibit-Timeplot Exception: time and value arrays of unequal size, unplottable";
}for(var b=0;
b<j.length;
b++){var h,g;
try{h=SimileAjax.DateTime.parseIso8601DateTime(j[b]).getTime();
}catch(c){throw"Exhibit-Timeplot Exception: cannot parse time";
}try{var g=parseFloat(d[b]);
}catch(c){throw"Exhibit-Timeplot Exception: cannot parse value";
}H.add(h);
if(!U[h]){U[h]={};
U[h][a]=g;
}else{U[h][a]=g;
}}K.add(a);
};
var Q=function(c,b){var a;
W.getValue(c,L,function(d){a=d;
return true;
});
var Z;
W.getSeriesConnector(c,L,function(d){Z=d;
return true;
});
var Y=b.getTime();
H.add(Y);
if(!U[Y]){U[Y]={};
U[Y][Z]=a;
}else{U[Y][Z]=a;
}K.add(Z);
};
F.visit(function(a){var Z;
O._getTime(a,L,function(b){Z=b;
return true;
});
if(Z){Q(a,Z);
}else{try{A(a);
}catch(Y){P.push(a);
}}});
var T=K.toArray();
var E=H.toArray();
this._legend=T;
E.sort(function(Z,Y){return Z-Y;
});
var J={};
for(var S=0;
S<E.length;
S++){var G=[];
for(var R=0;
R<T.length;
R++){var X=U[E[S]][T[R]];
if(X){G.push(parseFloat(X));
J[T[R]]=X;
}else{if(J[T[R]]){G.push(parseFloat(J[T[R]]));
}else{G.push(0);
}}}var D=SimileAjax.NativeDateUnit.fromNumber(parseInt(E[S]));
var M=new Timeplot.DefaultEventSource.NumericEvent(D,G);
B.push(M);
}var I=C-P.length;
if(I>this._largestSize){this._largestSize=I;
this._reconstructTimeplot();
this._eventSource.addMany(B);
}else{this._reconstructTimeplot();
this._eventSource.addMany(B);
}}this._dom.setUnplottableMessage(C,P);
};
