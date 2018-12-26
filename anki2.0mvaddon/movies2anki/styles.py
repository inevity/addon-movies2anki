front_template = """
<div class='media'>[sound:{{Video}}]</div>
"""

css = """
.card
{
  font-family: arial;
  font-size: 18px;
  text-align: center;
  color: black;
  background-color: white;
}

.expression
{
  font-size: 22px;
}

.meaning
{
  font-size: 18px;
  color: #000080;
}

.notes
{
  font-size: 18px;
}

.media
{
  margin: 0.15em;
}
"""

back_template = """
<div class='media'>[sound:{{Audio}}]</div>
<div class='expression'>{{Expression}}</div>
{{#Meaning}}
<hr>
<div class='meaning'>{{Meaning}}</div>
{{/Meaning}}
<div class='notes'>{{Notes}}</div>
"""

#  ------------------------------------- #

subs2srs_front_template = """
<div class='media'>[sound:{{Audio}}]</div>
<div class='media'>{{Snapshot}}</div>
<br />
<div class='expression'>{{Expression}}</div>
"""

subs2srs_css = """
.card
{
  font-family: arial;
  font-size: 18px;
  text-align: center;
  color: black;
  background-color: white;
}

.expression
{
  font-size: 22px;
}

.meaning
{
  font-size: 18px;
  color: #000080;
}

.notes
{
  font-size: 18px;
}

.media
{
  margin: 0.15em;
}
"""

subs2srs_back_template = """
{{FrontSide}}
<hr id=answer>
<div class='meaning'>{{Meaning}}</div>
<div class='notes'>{{Notes}}</div>
"""