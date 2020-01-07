var i = 0; /* Set Global Variable i */
function increment(){
i += 1; /* Function for automatic increment of field's "Name" attribute. */
}
/*
---------------------------------------------

Function to Remove Form Elements Dynamically
---------------------------------------------

*/
function removeElement(parentDiv, childDiv){
if (childDiv == parentDiv){
alert("The parent div cannot be removed.");
}
else if (document.getElementById(childDiv)){
var child = document.getElementById(childDiv);
var parent = document.getElementById(parentDiv);
parent.removeChild(child);
}
else{
alert("Child div has already been removed or does not exist.");
return false;
}
}

function createMIP(){
resetElements()
var r = document.createElement('span');
var y = document.createElement("INPUT");
var z = document.createElement('P');
y.setAttribute("type", "text");
increment();
y.setAttribute("Name", "textelement_" + i);
increment();
z.setAttribute("Name", "textelement_" + i);
z.innerHTML="Number of MIPs to be created in every subnet";
increment();
r.appendChild(y);
r.appendChild(z);
document.getElementById("myForm").appendChild(r);
}

function deleteMIP(){
resetElements()
var r = document.createElement('span');
var y = document.createElement("INPUT");
var z = document.createElement('P');
y.setAttribute('type', 'checkbox');
y.setAttribute("Name", "textelement_" + i);
increment();
z.setAttribute("Name", "textelement_" + i);
z.innerHTML="Select the Checkbox for deleting all the MIPs";
r.appendChild(y);
r.appendChild(z);
r.setAttribute("id", "id_" + i);
document.getElementById("myForm").appendChild(r);
}

function resetElements(){
document.getElementById('myForm').innerHTML = '';
}