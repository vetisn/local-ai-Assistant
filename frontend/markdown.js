/**
 * Markdown 流式渲染引擎 v8.3
 * 支持延迟初始化 + KaTeX 数学公式
 */
(function() {
    'use strict';

    // ========== 渲染器类 ==========
    class MarkdownRenderer {
        constructor() {
            this.ready = false;
            this.katexReady = false;
            this._init();
        }

        _init() {
            if (typeof marked !== 'undefined') {
                marked.setOptions({ 
                    gfm: true, 
                    breaks: true,
                    // 允许中文字符紧邻 ** 也能正确解析粗体
                    pedantic: false
                });
                this.ready = true;
            } else {
                console.warn('[MD] marked.js 未加载，将使用纯文本模式');
            }
            
            if (typeof katex !== 'undefined') {
                this.katexReady = true;
            } else {
                console.warn('[MD] KaTeX 未加载，数学公式将不渲染');
            }
        }

        // 确保初始化
        _ensureReady() {
            if (!this.ready && typeof marked !== 'undefined') {
                this._init();
            }
            if (!this.katexReady && typeof katex !== 'undefined') {
                this.katexReady = true;
            }
            return this.ready;
        }
        
        // 处理数学公式 - 在 Markdown 解析前保护公式
        _protectMath(text) {
            if (!text) return { text: '', formulas: [] };
            
            const formulas = [];
            let index = 0;
            
            // 保护 $$ ... $$ 块级公式（先处理块级，避免被行内匹配）
            text = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, formula) => {
                const placeholder = `%%MATH_BLOCK_${index}%%`;
                formulas.push({ placeholder, formula: formula.trim(), display: true });
                index++;
                return placeholder;
            });
            
            // 保护 \[ ... \] 块级公式
            text = text.replace(/\\\[([\s\S]+?)\\\]/g, (match, formula) => {
                const placeholder = `%%MATH_BLOCK_${index}%%`;
                formulas.push({ placeholder, formula: formula.trim(), display: true });
                index++;
                return placeholder;
            });
            
            // 保护 $ ... $ 行内公式（不跨行，避免匹配货币符号）
            text = text.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
                // 跳过看起来像货币的情况（如 $100）
                if (/^\d/.test(formula.trim())) {
                    return match;
                }
                const placeholder = `%%MATH_INLINE_${index}%%`;
                formulas.push({ placeholder, formula: formula.trim(), display: false });
                index++;
                return placeholder;
            });
            
            // 保护 \( ... \) 行内公式
            text = text.replace(/\\\(([\s\S]+?)\\\)/g, (match, formula) => {
                const placeholder = `%%MATH_INLINE_${index}%%`;
                formulas.push({ placeholder, formula: formula.trim(), display: false });
                index++;
                return placeholder;
            });
            
            // 处理独立的 LaTeX 命令（如 \sigma_m, \Delta K 等）
            text = text.replace(/\\(alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega|Alpha|Beta|Gamma|Delta|Epsilon|Zeta|Eta|Theta|Iota|Kappa|Lambda|Mu|Nu|Xi|Pi|Rho|Sigma|Tau|Upsilon|Phi|Chi|Psi|Omega|infty|partial|nabla|sum|prod|int|sqrt|frac|cdot|times|div|pm|mp|leq|geq|neq|approx|equiv|sim|propto|perp|parallel|angle|degree)(_\{[^}]+\}|_[a-zA-Z0-9]|\^\{[^}]+\}|\^[a-zA-Z0-9])*/g, (match) => {
                const placeholder = `%%MATH_INLINE_${index}%%`;
                formulas.push({ placeholder, formula: match, display: false });
                index++;
                return placeholder;
            });
            
            return { text, formulas };
        }
        
        // 还原并渲染数学公式
        _restoreMath(html, formulas) {
            if (!formulas || formulas.length === 0) return html;
            
            for (const item of formulas) {
                let rendered;
                if (this.katexReady) {
                    try {
                        rendered = katex.renderToString(item.formula, {
                            displayMode: item.display,
                            throwOnError: false,
                            output: 'html'
                        });
                    } catch (e) {
                        console.warn('[MD] KaTeX 渲染失败:', item.formula, e);
                        rendered = `<code class="math-error">${item.formula}</code>`;
                    }
                } else {
                    // KaTeX 未加载时显示原始公式
                    rendered = item.display 
                        ? `<div class="math-fallback">$$${item.formula}$$</div>`
                        : `<code class="math-fallback">$${item.formula}$</code>`;
                }
                html = html.replace(item.placeholder, rendered);
            }
            
            return html;
        }

        render(el, md, final = true) {
            if (!el) return false;
            
            // 尝试初始化
            this._ensureReady();
            
            // 如果 marked 未加载，使用纯文本模式
            if (!this.ready) {
                el.innerHTML = (md || '').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
                return true;
            }
            
            this._doRender(el, final ? md : this._fixIncomplete(md || ''), !final);
            return true;
        }

        _doRender(el, md, isStreaming = false) {
            try {
                // 预处理：修复中文字符紧邻 ** 的情况
                let processedMd = md || '';
                
                // 先保护数学公式
                const { text: protectedMd, formulas } = this._protectMath(processedMd);
                
                // 保护 XML 工具调用标签（防止被当作 HTML 处理）
                // 支持多种格式: <function_calls>, <| DSML | function_calls>, <function_calls> 等
                processedMd = protectedMd;
                const xmlToolCallPlaceholders = [];
                let xmlIndex = 0;
                
                // 匹配 function_calls 标签的各种变体
                processedMd = processedMd.replace(/<[\s\|]*(?:DSML\s*\|)?\s*(?:antml:)?(\/?)function_calls\s*>/gi, (match, slash) => {
                    const placeholder = `%%XML_TOOL_${xmlIndex}%%`;
                    xmlToolCallPlaceholders.push({ placeholder, original: match, isClose: !!slash });
                    xmlIndex++;
                    return placeholder;
                });
                
                // 匹配 invoke 标签的各种变体
                processedMd = processedMd.replace(/<[\s\|]*(?:DSML\s*\|)?\s*(?:antml:)?(\/?)invoke\s+/gi, (match, slash) => {
                    const placeholder = `%%XML_INVOKE_${xmlIndex}%%`;
                    xmlToolCallPlaceholders.push({ placeholder, original: match, isClose: !!slash });
                    xmlIndex++;
                    return placeholder;
                });
                
                // 匹配 invoke 结束标签
                processedMd = processedMd.replace(/<[\s\|]*(?:DSML\s*\|)?\s*(?:antml:)?\/invoke\s*>/gi, (match) => {
                    const placeholder = `%%XML_INVOKE_END_${xmlIndex}%%`;
                    xmlToolCallPlaceholders.push({ placeholder, original: match, isClose: true });
                    xmlIndex++;
                    return placeholder;
                });
                
                // 匹配 parameter 标签的各种变体
                processedMd = processedMd.replace(/<[\s\|]*(?:DSML\s*\|)?\s*(?:antml:)?(\/?)parameter\s+/gi, (match, slash) => {
                    const placeholder = `%%XML_PARAM_${xmlIndex}%%`;
                    xmlToolCallPlaceholders.push({ placeholder, original: match, isClose: !!slash });
                    xmlIndex++;
                    return placeholder;
                });
                
                // 匹配 parameter 结束标签
                processedMd = processedMd.replace(/<[\s\|]*(?:DSML\s*\|)?\s*(?:antml:)?\/parameter\s*>/gi, (match) => {
                    const placeholder = `%%XML_PARAM_END_${xmlIndex}%%`;
                    xmlToolCallPlaceholders.push({ placeholder, original: match, isClose: true });
                    xmlIndex++;
                    return placeholder;
                });
                
                let html = marked.parse(processedMd);
                
                if (typeof DOMPurify !== 'undefined') {
                    // 允许 KaTeX 生成的标签和属性，以及自定义协议链接
                    html = DOMPurify.sanitize(html, {
                        ADD_TAGS: ['semantics', 'annotation', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac', 'mroot', 'msqrt', 'mtext', 'mspace', 'mtable', 'mtr', 'mtd', 'mover', 'munder', 'munderover', 'math'],
                        ADD_ATTR: ['xmlns', 'encoding', 'mathvariant', 'stretchy', 'fence', 'separator', 'accent', 'accentunder', 'columnalign', 'rowalign', 'columnspacing', 'rowspacing', 'columnlines', 'rowlines', 'frame', 'framespacing', 'equalrows', 'equalcolumns', 'displaystyle', 'lspace', 'rspace', 'movablelimits', 'largeop', 'symmetric', 'maxsize', 'minsize', 'scriptlevel', 'linethickness', 'notation', 'open', 'close', 'separators', 'bevelled', 'numalign', 'denomalign', 'actiontype', 'selection', 'href', 'mathbackground', 'mathcolor', 'mathsize', 'width', 'height', 'depth', 'voffset', 'align', 'side', 'minlabelspacing', 'groupalign', 'charalign', 'stackalign', 'charspacing', 'longdivstyle', 'position', 'shift', 'location', 'crossout', 'length', 'leftoverhang', 'rightoverhang', 'mslinethickness', 'decimalpoint', 'edge', 'indentalign', 'indentalignfirst', 'indentalignlast', 'indentshift', 'indentshiftfirst', 'indentshiftlast', 'indenttarget', 'linebreak', 'linebreakmultchar', 'linebreakstyle', 'lineleading', 'infixlinebreakstyle', 'class', 'style', 'aria-hidden', 'download', 'target', 'rel'],
                        ADD_URI_SAFE_ATTR: ['href'],
                        ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|sandbox|file):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
                    });
                }
                
                // 还原 XML 工具调用标签（转义显示）
                xmlToolCallPlaceholders.forEach(item => {
                    const escaped = item.original.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    html = html.replace(item.placeholder, escaped);
                });
                
                // 还原并渲染数学公式
                html = this._restoreMath(html, formulas);
                
                el.innerHTML = html;
                
                // 代码高亮
                if (typeof hljs !== 'undefined') {
                    el.querySelectorAll('pre code').forEach(block => {
                        hljs.highlightElement(block);
                        // 手动高亮运算符（highlight.js 不处理）
                        this._highlightOperators(block);
                    });
                }
                // 流式渲染时也添加代码头部
                this._addStyles(el, true);
            } catch (e) {
                console.error('[MD] 渲染错误:', e);
                el.textContent = md;
            }
        }

        _addStyles(container, addHeaders = false) {
            container.querySelectorAll('pre').forEach(pre => {
                pre.classList.add('code-block');
                const code = pre.querySelector('code');
                if (code) {
                    let lang = 'text';
                    for (const cls of code.className.split(' ')) {
                        if (cls.startsWith('language-')) {
                            lang = cls.replace('language-', '');
                            break;
                        }
                    }
                    pre.dataset.lang = lang;
                    
                    // 不需要特殊处理滚轮事件，浏览器默认行为就是：
                    // 代码框内滚动到顶/底后，继续滚动会滚动页面
                }
                
                // 流式渲染时也添加头部
                if (addHeaders && !pre.querySelector('.code-header')) {
                    const lang = pre.dataset.lang || 'text';
                    const codeEl = pre.querySelector('code');
                    if (codeEl) {
                        const header = document.createElement('div');
                        header.className = 'code-header';

                        const langSpan = document.createElement('span');
                        langSpan.className = 'code-lang';
                        langSpan.textContent = lang.toUpperCase();
                        header.appendChild(langSpan);

                        const btn = document.createElement('button');
                        btn.className = 'code-copy-btn';
                        btn.textContent = '复制';
                        btn.onclick = (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            navigator.clipboard.writeText(codeEl.textContent || '').then(() => {
                                btn.textContent = '已复制';
                                setTimeout(() => { btn.textContent = '复制'; }, 2000);
                            });
                        };
                        header.appendChild(btn);
                        pre.insertBefore(header, pre.firstChild);
                    }
                }
            });

            container.querySelectorAll('code').forEach(code => {
                if (code.parentElement?.tagName !== 'PRE') {
                    code.classList.add('inline-code');
                }
            });

            container.querySelectorAll('a[href^="http"]').forEach(a => {
                a.setAttribute('target', '_blank');
                a.setAttribute('rel', 'noopener');
            });
        }

        _fixIncomplete(text) {
            if (!text) return '';
            const fenceCount = (text.match(/```/g) || []).length;
            if (fenceCount % 2 === 1) text += '\n```';
            const boldCount = (text.match(/\*\*/g) || []).length;
            if (boldCount % 2 === 1) text += '**';
            return text;
        }

        // 手动高亮运算符
        _highlightOperators(block) {
            const operators = /([+\-*/%]|[<>]=?|[=!]=|={1,3}|&{1,2}|\|{1,2}|\^|~|<<|>>|:)/g;
            const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, null, false);
            const textNodes = [];
            while (walker.nextNode()) {
                textNodes.push(walker.currentNode);
            }
            textNodes.forEach(node => {
                // 跳过已经在 hljs span 内的文本（如字符串、注释等）
                if (node.parentElement && node.parentElement.className && 
                    node.parentElement.className.includes('hljs-')) {
                    return;
                }
                const text = node.textContent;
                if (operators.test(text)) {
                    operators.lastIndex = 0; // 重置正则
                    const fragment = document.createDocumentFragment();
                    let lastIndex = 0;
                    let match;
                    while ((match = operators.exec(text)) !== null) {
                        if (match.index > lastIndex) {
                            fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
                        }
                        const span = document.createElement('span');
                        span.className = 'hljs-operator';
                        span.textContent = match[0];
                        fragment.appendChild(span);
                        lastIndex = match.index + match[0].length;
                    }
                    if (lastIndex < text.length) {
                        fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
                    }
                    if (lastIndex > 0) {
                        node.parentNode.replaceChild(fragment, node);
                    }
                }
            });
        }

        cancel(el) {}

        addCopyButtons(container) {
            if (!container) return;
            container.querySelectorAll('pre.code-block').forEach(pre => {
                if (pre.querySelector('.code-header')) return;
                const lang = pre.dataset.lang || 'text';
                const code = pre.querySelector('code');
                if (!code) return;

                const header = document.createElement('div');
                header.className = 'code-header';

                const langSpan = document.createElement('span');
                langSpan.className = 'code-lang';
                langSpan.textContent = lang.toUpperCase();
                header.appendChild(langSpan);

                const btn = document.createElement('button');
                btn.className = 'code-copy-btn';
                btn.textContent = '复制';
                btn.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    navigator.clipboard.writeText(code.textContent || '').then(() => {
                        btn.textContent = '已复制';
                        setTimeout(() => { btn.textContent = '复制'; }, 2000);
                    });
                };
                header.appendChild(btn);
                pre.insertBefore(header, pre.firstChild);
                

            });
        }

        parse(md) {
            // 确保初始化
            this._ensureReady();
            if (!this.ready) return md;
            try {
                // 先保护数学公式
                const { text: protectedMd, formulas } = this._protectMath(md || '');
                
                let html = marked.parse(protectedMd);
                if (typeof DOMPurify !== 'undefined') {
                    html = DOMPurify.sanitize(html, {
                        ADD_TAGS: ['semantics', 'annotation', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac', 'mroot', 'msqrt', 'mtext', 'mspace', 'mtable', 'mtr', 'mtd', 'mover', 'munder', 'munderover', 'math'],
                        ADD_ATTR: ['xmlns', 'encoding', 'mathvariant', 'stretchy', 'class', 'style', 'aria-hidden', 'href', 'download', 'target', 'rel'],
                        ADD_URI_SAFE_ATTR: ['href'],
                        ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|sandbox|file):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
                    });
                }
                
                // 还原并渲染数学公式
                html = this._restoreMath(html, formulas);
                
                return html;
            } catch (e) {
                return md;
            }
        }
    }

    // ========== 导出 ==========
    const renderer = new MarkdownRenderer();

    window.MarkdownEngine = {
        renderToEl: (el, markdown, isComplete = true) => renderer.render(el, markdown, isComplete),
        renderStreaming: (el, markdown) => renderer.render(el, markdown, false),
        renderFinal: (el, markdown) => renderer.render(el, markdown, true),
        cancelRender: (el) => renderer.cancel(el),
        addCopyButtons: (container) => renderer.addCopyButtons(container),
        parse: (markdown) => renderer.parse(markdown),
        // 兼容旧代码：render 作为 parse 的别名，返回 HTML 字符串
        render: (markdown) => renderer.parse(markdown),
        isReady: () => renderer._ensureReady()
    };
})();
