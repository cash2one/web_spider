#!/usr/bin/env python
# -*- encoding: utf-8 -*-


from httpbin import app


#普通链接

@app.route("/ajax_link.php", methods=["POST", "GET"])
def test_ajax_php_link():
    return '''
    ajax_link.php
'''

#普通链接
@app.route("/html_link")
def test_html_link():
    return '''
    <div class=demo>
<a href="html_link1.php?id=2">html_link1</a>
<a href="html_link2.php?id=4">html_link2</a>
<a href="html_link21.php?id=展示">html_link3</a>
</div>

'''

#js生成的链接
@app.route('/js')
def test_js():
    return '''
<div class=demo id=jsCode>
<a id="l1"  >js_link1</a>
<a id="l2"  >js_link2</a>
<script>
l1.href = "js_link1.php"+"?id=1&msg=abc";
l2.href = "js_link2.php"+"?id=2&msg=哇";
</script>
</div>
'''

#表单
@app.route("/form")
def test_form():
    return '''
    <div class=demo id=formCode>
<form method="post" name="form1" enctype="multipart/form-data"  action="post_link.php">
<script>
document.write('<input type="text" name="i'+'d" size="30" value=1><br>');
document.write('<input type="text" name="m'+'sg" size="30" value="abc">');
</script>
<input type="submit" value="提交" name="B1">
</form>
</div>
    '''

#人机交互生成链接 click_link.php?id=1
@app.route('/click')
def test_click():
    return '''
<div class=demo id=clickCode>
<div id=abc>-</div>
<input type=button id=1 onclick="abc.innerHTML ='<a href=click_link3.php'+'?id=3>click_link3.php?id=3</a>'" value="点击后生成链接(click_link3.php?id=3)"/>
<input type=button id=1 onclick="abc.innerHTML ='<a href=click_link1.php'+'?id=1>click_link1.php?id=1</a>'" value="点击后生成链接(click_link1.php?id=1)"/>
<input type=button id=1 onclick="abc.innerHTML ='<a href=click_link2.php'+'?id=2>click_link2.php?id=2</a>'" value="点击后生成链接(click_link2.php?id=2)"/>
</div>
'''

#ajax_link.php?id=1&t=
@app.route('/ajax')
def test_ajax():
    return '''
<div class=demo id=ajaxCode>
<script>
if(window.ActiveXObject) ajax=new ActiveXObject("Microsoft.XMLHTTP");
else ajax=new XMLHttpRequest();
ajax.open('get',"ajax_link.php?id=1&t="+Math.random(),false);
ajax.send();
document.write("ajax.ResponseText length:"+ajax.responseText.length);
</script>
</div>
'''


@app.route('/pyspider/test.html')
def test_page():
    return '''
    <div id=abc>-</div>
    <input type=button id=1 onclick="abc.innerHTML ='<a href=/pyspider/click11111111.html>click1</a>';console.log('Click111');" value="点击后生成链接(1)"/>
    <input type=button id=2 onclick="abc.innerHTML ='<a href=/pyspider/c22222222.html>click2</a>';console.log('Click22222');" value="点击后生成链接(2)"/>
<a href="/pyspider/test.html">404</a>
<a href="/links/10/0">0</a>
<a href="/links/10/1">1</a>
<a href="/links/10/2">2</a>
<a href="/links/10/3">3</a>
<a href="/links/10/4">4</a>
<a href="/gzip">gzip</a>
<a href="/get">get</a>
<a href="/deflate">deflate</a>
<a href="/html">html</a>
<a href="/xml">xml</a>
<a href="/robots.txt">robots</a>
<a href="/cache">cache</a>
<a href="/stream/20">stream</a>
'''



@app.route('/ajax_click.html')
def test_ajax_click():
    return '''
<div class=status>loading...</div>
<div class=ua></div>
<div class=ip></div>
<a href="javascript:void(0)" onclick="load()">load</a>
<script>
function load() {
    var xhr = new XMLHttpRequest();
    xhr.onload = function() {
      var data = JSON.parse(xhr.responseText);
      document.querySelector('.status').innerHTML = 'done';
      document.querySelector('.ua').innerHTML = data.headers['User-Agent'];
      document.querySelector('.ip').innerHTML = data.origin;
    }
    xhr.open("get", "/get", true);
    xhr.send();
}
</script>
'''
