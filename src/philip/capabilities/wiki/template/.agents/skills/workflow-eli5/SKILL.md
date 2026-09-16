---
name: eli5
description: Explain a topic like I'm a 5 year old. Use when the user types /eli5 <topic> or asks for a dead-simple picture explainer of how something works. Do NOT use when the audience needs precision or technical depth — the everyday-analogy skeleton deliberately trades accuracy for clarity.
---

# ELI5 · 把任何东西讲给 5 岁小孩听

> Explain like I'm someone who knows nothing about this topic, using a HTML artifact with big pictures and few words.

**触发方式：**
- 用户输入 `/eli5 <topic>`（如 `/eli5 cache`、`/eli5 什么是差分隐私`）
- 用户说"像 5 岁小孩一样解释 X"、"用最简单的说法讲清楚 X"、"dead-simple 讲一下 X 怎么工作的"

## 核心原则

这是给**完全零基础**的人看的，不是简化教程，更不是术语表的缩短版：

1. **大图**：一个观点一张图。用超大 emoji、简单 SVG、日常类比（厨房、玩具、快递、冰箱）当主角。图能表达就不写字。
2. **少字**：一句话一个想法，用最日常的词汇。全篇词汇量控制在几百字以内，能砍就砍。
3. **真零基础**：假设读者对主题毫无概念，不使用任何未解释的术语。如果要引入术语，必须用比喻或括号人话先解释。
4. **HTML artifact**：最终产出一个自包含的 HTML 文件（内联样式、可独立打开），图文并茂。

## 工作流

### 1. 定位主题核心

先用一句话写下"这个东西到底是什么"（像一个 5 岁小孩会问的"它有什么用"）。如果写不出这句话，说明自己还没搞懂，先去查清再继续。

### 2. 找一个日常类比

从厨房 / 玩具 / 快递 / 冰箱 / 操场等生活场景里找一个"就是这个感觉"的类比。这个类比是整个 artifact 的骨架，后面所有内容都挂在它上面。

**类比示例：**
- 缓存 = 桌上常备的便签，不用每次都跑仓库翻
- 负载均衡 = 奶茶店排队，哪个窗口空去哪个
- 加密 = 上了锁的盒子，钥匙只有你和对方有
- 数据库索引 = 书的目录页，不用翻完整本书找一句话

### 3. 搭 HTML artifact 骨架

单文件、内联 CSS、不依赖外部资源。结构大约：

```html
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>缓存是什么 · ELI5</title>
  <style>/* 大字号、高对比、留白多的童书风 */</style>
</head>
<body>
  <!-- 每屏一个观点：超大图 + 一行字 -->
</body>
</html>
```

### 4. 写内容（每屏 = 一图 + 一句）

- **标题屏**：用类比句点题，比如"缓存 = 桌上的便签"
- **正文屏**：从上到下，一次只讲一个点，每个点配一张大图 + 一行短字
- **收尾屏**：用一句话收束，"现在你知道了，X 就是 Y"

每屏遵守「图大于字」：图占画面主体，文字最多一两行。

### 5. 自检

- 去掉所有图，剩下的话还能不能完整表达？→ 不能，因为图就是正文的一部分
- 有没有任何一句，5 岁小孩会问"这是什么意思"？→ 有就拆开或换说法
- 词汇量是否明显超出了一个零基础读者的耐心？→ 超了就再砍
- HTML 能直接双击打开且无报错？→ 确认过再交付

## 交付

把 HTML artifact 完整呈现给用户（代码块或直接预览），可附一句"核心就是：`<类比句>`"。不要写一长篇解释——artifact 本身就是全部内容。
