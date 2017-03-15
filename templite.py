#coding: utf-8
'''
学习代码: <<500 lines or less>>: template-engine
项目地址: https://github.com/aosabook/500lines
中文翻译地址: http://www.jianshu.com/p/b5d4aa45e771
'''
import re
__author__ = 'liyinggang'

class CodeBulider(object):
    '''
    一个python代码生成器
    '''
    STEP = 4 #一次缩进的步数
    def __init__(self,indent=0):
        '''
        - indent_level: 缩进级别
        - code: 由字符串代码或者CodeBulider对象组成的列表
        '''
        self.code = []
        self.indent_level = indent
    # 将 code list 变成字符串
    # 如果用 print CodeBulider的实例对象 或者调用 str(CodeBulider的实例对象)就会自动调用该方法
    def __str__(self):
        return ''.join(str(c) for c in self.code)
    #增加代码缩进
    def add_indent(self):
        self.indent_level += self.STEP
    # 减少代码缩进
    def sub_indent(self):
        self.indent_level -= self.STEP
    # 向code list 中添加一行代码,此代码包含缩进与换行
    def add_line(self,line):
        line = [" "*self.indent_level+line+'\n']
        self.code.extend(line)
    # 这个方法我认为是这里用得最妙的一处,为代码保存一处参考位置,为以后添加代码提供方便
    # 因为我们这个模板里面的变量是根据传入的 html 模板分析生成的,所以要保存一个位置放置变量名
    def add_section(self):
        '''测试如下代码可以了解此函数的作用
        code = CodeBulider()
        var_code = code.add_section()
        code.add_line('def three():')
        code.add_indent()
        code.add_line('return a+b')
        code.sub_indent()
        var_code.add_line('a = 1')
        var_code.add_line('b = 2')
        print code
        '''
        section = CodeBulider(self.indent_level)
        self.code.append(section)
        return section

    def get_global(self):
        # 确保整个代码结束后的缩进等级为 0
        assert self.indent_level == 0
        code = str(self) #获得python代码
        namespace = {}
        exec(code,namespace) #exec函数执行一串包含python代码的字符串，它的第二个参数是一个字典，用来收集字符串代码中定义的全局变量。
        # 可以用 add_section 中提供的代码来进行测试 :
        #>> print code.get_global()['a'] 的结果为 1
        return namespace

class TempliteError(Exception):
    pass

class Templite(object):
    def __init__(self,text=None,*contexts):# *号表示参数数量不受限制,python会通过解包来解析传入的参数
        self.text = text
        self.contexts = {}
        for context in contexts:
            self.contexts.update(context)
        self.all_vars = set() #保存程序中出现过的所有变量
        self.loop_vars = set() # 循环变量要去除掉,因为循环变量是在循环体内定义的
        code = CodeBulider()
        code.add_line('def render_function(context, do_dots):')
        code.add_indent()
        vars_code = code.add_section() #为以后插入变量名留一块参考位置
        code.add_line('result=[]')
        code.add_line('append_result = result.append') #微优化,节省了少量的时间，因为避免了再花时间去查找对象的append属性
        code.add_line('extend_result = result.extend') #同上微优化
        code.add_line('to_str = str') #防止变量名冲突

        #代码缓冲区
        buffered = []
        def flush_output():
            if len(buffered)==1:
                code.add_line('append_result(%s)'%(buffered[0]))
            elif len(buffered)>1:
                code.add_line('extend_result([%s])'% ",".join(buffered))
            del buffered[:]  #删除缓冲数组

        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text) # (?s) 即Singleline(单行模式)
        Stack = [] #操作符栈: if <-> endif | for <-> endfor
        for token in tokens:
            if token.startswith('{#'):
                #注释
                buffered.append(repr("<!-- %s -->") % token[2:-2])
            elif token.startswith('{%'): # 其中包含 1.if 2.for 3.endif 4.endfor 分情况讨论
                flush_output() #首先需要刷新一下缓冲区
                words = token[2:-2].strip().split()
                if words[0]=='if':
                    if len(words)!=2: #这里的if条件里面只能放一个条件,虽然我觉得不怎么合理...以后再完善
                        self._syntax_error("syntax error",token)
                    Stack.append('if')
                    code.add_line('if %s:'%(self.expr_code(words[1])))
                    code.add_indent() #增加缩进
                elif words[0]=='for':
                    if len(words)!=4:
                        self._syntax_error("syntax error",token)
                    Stack.append('for')
                    self.validate(words[1],self.loop_vars) #将循环变量words[1]合法性检测以及添加到loop_vars
                    code.add_line('for c_%s in %s:'%(words[1],self.expr_code(words[3])))
                    code.add_indent()
                elif words[0]=='endif':
                    top_word = Stack.pop()
                    if top_word!='if' or len(words)!=1:
                        self._syntax_error("syntax error",token)
                    code.sub_indent() #减少缩进
                elif words[0]=='endfor':
                    top_word = Stack.pop()
                    if top_word!='for' or len(words)!=1:
                        self._syntax_error("syntax error",token)
                    code.sub_indent()
                else:
                    self._syntax_error("syntax error",token)
            elif token.startswith('{{'):
                words = token[2:-2].strip()
                buffered.append("to_str(%s)" % self.expr_code(words))
            else:
                if token:
                    buffered.append(repr(token)) # repr(s)可以提供了字符串的引用,并且在需要的地方提供反斜杠 比如 '->\'

        # 如果栈没清空,证明有if-endif 或者 for-endfor 没成对出现
        if Stack:
            self._syntax_error("syntax error",Stack[-1])

        flush_output() #将缓冲区清空
        # 为 vars_code 添加变量名,因为循环变量不需要被定义,所以要去除掉循环变量,变量的初值由传入的context所提供
        # 生成的所有变量名前面都有 c_ ,防止与python内置变量名冲突
        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line('c_%s = context[%r]'%(var_name,var_name))

        code.add_line('return "".join(result)')
        code.sub_indent() #整个代码框架到此结束
        # 编译代码:这里只编译一次便可以多次使用
        self.code = code #测试生成的代码
        self.render_function = code.get_global()['render_function']

    def _syntax_error(self, msg, thing):
        '''
        处理报错信息
        '''
        raise TempliteError("%s: %r" % (msg, thing))

    def get_model_code(self):
        return self.code

    def expr_code(self,expr):
        '''解释代码
        | : 通道,参数为 变量名|过滤器1|过滤器2...
        . : 包含点操作符,交给点操作函数处理
        普通变量: 直接处理
        '''
        if '|' in expr:
            words = expr.split('|')
            code = self.expr_code(words[0]) #递归调用解释程序
            for func in words[1:]:#过滤器后面的就全部是函数了
                self.validate(func,self.all_vars)
                code = "c_%s(%s)"%(func,code)
        elif '.' in expr:
            words = expr.split('.')
            code = self.expr_code(words[0]) #递归调用解释程序
            args = ",".join(repr(c) for c in words[1:])
            code = "do_dots(%s,%s)" % (code,args)
        else:
            self.validate(expr,self.all_vars)
            code = "c_%s" % expr
        return code

    def validate(self,word,var_set):
        '''
        判断变量的合法性,必须以 '_'或者大小写英文字母开头，只包含 '_' 大小写字母以及数字
        '''
        if not re.match(r'[_a-zA-Z][_0-9a-zA-Z]*$',word):
            # 异常报错
            self._syntax_error("var_name is invalid",word)
        var_set.add(word) #注意 set 是用 add 方法添加元素

    def do_dots(self,expr,*args):
        '''
        实现点操作,html里面的点操作在Python中可能会有三种可能实现
        1: value = x['y']
        2: value = getattr(obj, "attribute") <=> value = obj.attribute
        3: value = value() #用 callable 来测试value 是否是能够调用的函数
        '''
        for word in args:
            try:
                expr = expr[word]
            except:
                expr = getattr(expr,word)
            if callable(expr):
                expr = expr()
        return expr

    def render(self,context=None):
        if context: #如果有context传入,合并
            self.contexts.update(context)
        return self.render_function(self.contexts,self.do_dots)

if __name__ == '__main__':
    # Make a Templite object.
    # 这个模板里面的name 将会使用 str.upper 函数变成大写
    templite = Templite('''
        <h1>Hello {{name|upper}}!</h1>
        {% for product in products %}
            <p>{{product.name}}:{{product.price}}</p>
        {% endfor %}
        {# loop #}
        {% if name %}
            <p>{{name.lower.upper}}<p>
        {% endif %}
        ''',
        {'upper':str.upper},
        {'lower':str.lower},
    )

    text = templite.render({
        'name': "Lee",
        'products': (
                    {'name':'Python','price':'$32.8'},
                    {'name':'C++','price':'$35.5'},
                    {'name':'Java','price':'$21.5'},
                    ),
    })
    with open("template_result.html",'w') as f:
        f.write(text)
    print templite.get_model_code()
    print text
