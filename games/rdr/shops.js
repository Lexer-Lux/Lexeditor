"use strict";
  const SHOP_FIELDS=[
    {field:"PriceModifier",key:"priceModifier",label:"Price modifier",step:"0.01",min:"0",max:"1000",help:"Multiplier applied to the base item price"},
    {field:"QuantityPerPurchase",key:"quantityPerPurchase",label:"Quantity per purchase",step:"1",min:"0",max:"2147483647",help:"Units received for one purchase"},
    {field:"TotalAvailableQuantity",key:"totalAvailableQuantity",label:"Available stock",step:"1",min:"-1",max:"2147483647",help:"-1 is reserved for records that use unlimited stock"}
  ];
  function matchingShops(){const needle=state.shopQuery.trim().toLowerCase();return (state.shops?.rows||[]).filter(item=>(!needle||[item.name,item.shop,item.category].some(value=>String(value||"").toLowerCase().includes(needle)))&&(!state.shopName||item.shop===state.shopName)&&(!state.shopCategory||item.category===state.shopCategory));}
  function shopBaseline(item,field){
    const value=item[field.key];
    if(field.key!=="priceModifier"||!Number.isFinite(value))return String(value);
    // Show the shortest decimal which represents the stored float32 value.
    for(let digits=1;digits<=9;digits++){const text=String(Number(value.toPrecision(digits)));if(Math.fround(Number(text))===value)return text;}
    return String(value);
  }
  function shopValue(item,field){const key=`${item.id}|${field.field}`;return Object.prototype.hasOwnProperty.call(state.shopEdits,key)?state.shopEdits[key]:shopBaseline(item,field);}
  function editShop(item,field,value){const key=`${item.id}|${field.field}`;if(value===shopBaseline(item,field))delete state.shopEdits[key];else state.shopEdits[key]=value;shell.refresh();}
  function selectShopItem(item){state.shopSelected=item.id;renderShops();}
  const SHOP_COLUMNS=[
    {key:"name",label:"Item",width:"minmax(0,1.35fr)",render:item=>cell(item.name)},
    {key:"shop",label:"Shop",width:"minmax(0,1.05fr)",render:item=>cell(item.shop)},
    {key:"category",label:"Type",width:"minmax(0,.7fr)",render:item=>cell(item.category)},
    {key:"stock",label:"Qty / Stock",width:"minmax(0,.8fr)",render:item=>cell(`x${item.quantityPerPurchase} / ${item.totalAvailableQuantity}`)}];
  function shopDetail(){
    const item=(state.shops?.rows||[]).find(row=>row.id===state.shopSelected);
    if(!item)return LexeditorUI.detailPanel({className:"record-detail shop-detail",title:"Select a shop item",body:[LexeditorUI.detailNote("Edits create a packed WGD override. The installed gringores.rpf stays unchanged.")]});
    return LexeditorUI.detailPanel({className:"record-detail shop-detail",title:item.name,actions:projectBadge(item),body:[
      detailField("Shop",shown(item.shop)),detailField("Stock type",shown(item.category)),
      detailField("Root hash",shown(item.rootHash)),
      detailField("Vanilla resource",shown(item.sourcePath)),
      detailField("Project override",shown(item.projectPath)),
      LexeditorUI.notice({title:"Live ShopInventory fields.",message:"The save preserves the other Gringo components and packs a verified resource override."}),
      ...SHOP_FIELDS.map(field=>{const control=el("input",{type:"number",step:field.step,min:field.min,max:field.max,value:shopValue(item,field),disabled:state.activeSource!=="mine",oninput:event=>editShop(item,field,event.target.value)}),vanilla=state.vanilla.shops?.rows?.find(row=>row.id===item.id)?.[field.key];return detailField(field.label,sourceControl(control,()=>shopValue(item,field),vanilla===undefined?undefined:String(vanilla),value=>editShop(item,field,String(value))),field.help)})
    ]});
  }
  function renderShops(){
    const rows=matchingShops();
    const shopNames=[...new Set((state.shops?.rows||[]).map(item=>item.shop))].sort((a,b)=>a.localeCompare(b));
    const categories=[...new Set((state.shops?.rows||[]).map(item=>item.category))].sort((a,b)=>a.localeCompare(b));
    $("#toolbar").replaceChildren();
    const shopFilter=el("select",{"aria-label":"Filter shop stock by shop",onchange:event=>{state.shopName=event.target.value;state.shopPage=0;renderShops();}},el("option",{value:"",selected:!state.shopName},"All shops"),...shopNames.map(name=>el("option",{value:name,selected:name===state.shopName},name)));
    const categoryFilter=el("select",{"aria-label":"Filter shop stock by type",onchange:event=>{state.shopCategory=event.target.value;state.shopPage=0;renderShops();}},el("option",{value:"",selected:!state.shopCategory},"All stock types"),...categories.map(category=>el("option",{value:category,selected:category===state.shopCategory},category)));
    $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec(state.shopEdits,()=>{state.shopPage=0}),rows,key:item=>item.id,slots:false,page:state.shopPage,pageSize:state.shopPageSize,selected:state.shopSelected,noun:"items",splitKey:"rdr-shops",className:"rdr-split",defaultSplit:44,fit:{minRowHeight:32},
      search:{key:"rdr-shops",value:state.shopQuery,placeholder:"Search RDR shop stock…",change:value=>{state.shopQuery=value;state.shopPage=0;renderShops();}},filters:[shopFilter,categoryFilter],
      master:({rows,selected,select})=>columnList({rows,key:item=>item.id,columns:SHOP_COLUMNS,selected,selectedClass:"sel",select,class:"rdr-record-list","aria-label":"RDR shop inventory"}),
      detail:()=>shopDetail(),sync:next=>{state.shopPage=next.page;state.shopPageSize=next.pageSize;state.shopSelected=next.selected||"";},change:next=>{state.shopPage=next.page;state.shopPageSize=next.pageSize;state.shopSelected=next.selected||"";renderShops();}}));shell.refresh();
  }
