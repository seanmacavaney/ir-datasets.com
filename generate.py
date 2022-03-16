from mako.template import Template
import json
import pkgutil
import io
import os
import sys
import typing
import argparse
import datetime
from contextlib import contextmanager
from pathlib import Path
from enum import Enum
import ir_datasets


COMMON_HEAD = '''
<link rel="stylesheet" href="main.css" />
<script src="https://code.jquery.com/jquery-1.12.4.min.js" integrity="sha256-ZosEbRLbNQzLpnKIkEdrPv7lOy9C27hHQ+Xp8a4MxAQ=" crossorigin="anonymous"></script>
<script src="https://code.jquery.com/ui/1.12.1/jquery-ui.min.js" integrity="sha256-VazP97ZCwtekAsvgPBSUwPFKdrwD3unUfSGVYrahUqU=" crossorigin="anonymous"></script>
<script src="main.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1" />
'''


def main():
    os.environ['IR_DATASETS_SKIP_DEPRECATED_WARNING'] = 'true'
    parser = argparse.ArgumentParser(prog='generate.py', description='Generates documentation files.')
    parser.add_argument('--out_dir', default='./docs')
    parser.add_argument('--release', action='store_true')

    args = parser.parse_args()
    out_dir = args.out_dir

    versions = [f'v{ir_datasets.__version__}', ''] if args.release else ['master']

    for version in versions:
        if version:
            os.makedirs(f'{args.out_dir}/{version}', exist_ok=True)

        generate_python_docs(args.out_dir, version)
        generate_cli_docs(args.out_dir, version)
        generate_redirect(args.out_dir, version, 'datasets.html', 'index.html')
        generate_redirect(args.out_dir, version, 'all.html', 'index.html')
        generate_downloads(args.out_dir, version)
        generate_integrations(args.out_dir, version)
        generate_css(args.out_dir, version)
        generate_js(args.out_dir, version)
        generate_bib(args.out_dir, version)

        top_level = [name for name in sorted(ir_datasets.registry) if '/' not in name]
        top_level_map = {t: [] for t in top_level}
        for name in sorted(ir_datasets.registry):
            dataset = ir_datasets.registry[name]
            parent = name.split('/')[0]
            if parent != name:
                top_level_map[parent].append((name, dataset))

        generate_index(args.out_dir, version, top_level_map)
        generate_counts(args.out_dir, version, top_level_map)

        bibliography = pkgutil.get_data('ir_datasets', 'docs/bibliography.bib').decode().split('\n\n')
        bibliography = {b.split('{')[1].split(',')[0]: b for b in bibliography}

        for top_level in sorted(top_level_map):
            generate_dataset_page(args.out_dir, version, top_level, top_level_map[top_level], bibliography)
    generate_github_action(top_level_map)


def generate_dataset_page(out_dir, version, top_level, sub_datasets, bibliography):
    dataset = ir_datasets.registry[top_level]
    documentation = dataset.documentation() if hasattr(dataset, 'documentation') else {}
    with page_template(f'{top_level}.html', out_dir, version, title=documentation.get('pretty_name', top_level), source=f'datasets/{top_level.replace("-", "_")}.py') as out:
        data_access_section = generate_data_access_section(documentation)
        index = '\n'.join(f'<li><a href="#{name}"><kbd><span class="prefix">{top_level}</span>{name[len(top_level):]}</kbd></a></li>' for name, ds in sub_datasets)
        out.write(f'''
<div style="font-weight: bold; font-size: 1.1em;">Index</div>
<ol class="index">
<li><a href="#{top_level}"><kbd>{top_level}</kbd></a></li>
{index}
</ol>
<div id="Downloads">
</div>
{data_access_section}<hr />
<div class="dataset" id="{top_level}">
<h3><kbd class="select"><span class="str">"{top_level}"</span></kbd></h3>
{generate_dataset(dataset, top_level, bibliography)}
</div>
''')
        for name, dataset in sub_datasets:
            out.write(f'''
<hr />
<div class="dataset" id="{name}" data-parent="{top_level}">
<h3><kbd class="ds-name select"><span class="str">"{name}"</span></kbd></h3>
{generate_dataset(dataset, name, bibliography)}
</div>
''')
        out.write('''
<script type="text/javascript">
$(function () {
    $.ajax({
        'url': 'https://ir-datasets.com/dlc/''' + top_level + '''.json'
    }).done(function (data) {
        $('#Downloads').append(generateDownloads('Downloadable content', data));
    });
});
</script>
''')



def generate_dataset(dataset, dataset_id, bibliography):
    import example_generators
    generators = {
        ('Python API', 'irds-python'): example_generators.PythonExampleGenerator(dataset_id),
        ('CLI', 'irds-cli'): example_generators.CliExampleGenerator(dataset_id),
        ('PyTerrier', 'pyterrier'): example_generators.PyTerrierExampleGenerator(dataset_id),
    }
    with io.StringIO() as out:
        if hasattr(dataset, 'documentation'):
            documentation = dataset.documentation()
        else:
            documentation = {}
        if 'desc' not in documentation:
            print(f'no description for {dataset_id}')
        desc = documentation.get('desc', '<p><i>(no description provided)</i></p>')
        tags = []
        tags = ' '.join(f'<span class="tag tag-{t}" data-fields="{", ".join(c._fields)}">{t}</span>' for t, c in tags)
        measures = ''
        if 'official_measures' in documentation:
            measures = ', '.join([f'<a href="https://ir-measur.es/en/latest/measures.html"><kbd>{m}</kbd></a>' for m in documentation['official_measures']])
            measures = f'<p>Official evaluation measures: {measures}</p>'
        deprecated = ''
        if hasattr(dataset, 'deprecated'):
            deprecated = f'<div class="warn">{dataset.deprecated()}</div>'
        out.write(f'''{deprecated}
<div class="desc">
{desc}{measures}
</div>
''')
        out.write('<div class="tabs">')
        if dataset.has_queries():
            parent_ds = ir_datasets.queries_parent_id(dataset_id)
            parent_ds_note = ''
            if parent_ds != dataset_id:
                parent_ds_note = f'<p>Inherits queries from <a class="ds-ref">{parent_ds}</a></p>'
            count = ds_count_value
            out.write(f'''
<a class="tab" target="{dataset_id}__queries">queries</a>
<div id="{dataset_id}__queries" class="tab-content">
{ds_page_count(dataset, dataset_id, "queries")}
{parent_ds_note}
<p>Language: {_lang(dataset.queries_lang())}</p>
<div>Query type:</div>
{generate_data_format(dataset.queries_cls())}
{generate_examples(generators, 'generate_queries')}
</div>
''')
        if dataset.has_docs():
            parent_ds = ir_datasets.docs_parent_id(dataset_id)
            parent_ds_note = ''
            if parent_ds != dataset_id:
                parent_ds_note = f'<p>Inherits docs from <a class="ds-ref">{parent_ds}</a></p>'
            out.write(f'''
<a class="tab" target="{dataset_id}__docs">docs</a>
<div id="{dataset_id}__docs" class="tab-content">
{ds_page_count(dataset, dataset_id, "docs")}
{parent_ds_note}
<p>Language: {_lang(dataset.docs_lang())}</p>
<div>Document type:</div>
{generate_data_format(dataset.docs_cls())}
{generate_examples(generators, 'generate_docs')}
</div>
''')
        if dataset.has_qrels():
            parent_ds = ir_datasets.qrels_parent_id(dataset_id)
            parent_ds_note = ''
            if parent_ds != dataset_id:
                parent_ds_note = f'<p>Inherits qrels from <a class="ds-ref">{parent_ds}</a></p>'
            out.write(f'''
<a class="tab" target="{dataset_id}__qrels">qrels</a>
<div id="{dataset_id}__qrels" class="tab-content">
{ds_page_count(dataset, dataset_id, "qrels")}
{parent_ds_note}
<div>Query relevance judgment type:</div>
{generate_data_format(dataset.qrels_cls())}
<p>Relevance levels</p>
{generate_qrel_defs_table(dataset)}
{generate_examples(generators, 'generate_qrels')}
</div>
''')
        if dataset.has_scoreddocs():
            parent_ds = ir_datasets.scoreddocs_parent_id(dataset_id)
            parent_ds_note = ''
            if parent_ds != dataset_id:
                parent_ds_note = f'<p>Inherits scoreddocs from <a class="ds-ref">{parent_ds}</a></p>'
            out.write(f'''
<a class="tab" target="{dataset_id}__scoreddocs">scoreddocs</a>
<div id="{dataset_id}__scoreddocs" class="tab-content">
{ds_page_count(dataset, dataset_id, "scoreddocs")}
{parent_ds_note}
<div>Scored Document type:</div>
{generate_data_format(dataset.scoreddocs_cls())}
{generate_examples(generators, 'generate_scoreddocs')}
</div>
''')
        if dataset.has_docpairs():
            parent_ds = ir_datasets.docpairs_parent_id(dataset_id)
            parent_ds_note = ''
            if parent_ds != dataset_id:
                parent_ds_note = f'<p>Inherits docpairs from <a class="ds-ref">{parent_ds}</a></p>'
            out.write(f'''
<a class="tab" target="{dataset_id}__docpairs">docpairs</a>
<div id="{dataset_id}__docpairs" class="tab-content">
{ds_page_count(dataset, dataset_id, "docpairs")}
{parent_ds_note}
<div>Document Pair type:</div>
{generate_data_format(dataset.docpairs_cls())}
{generate_examples(generators, 'generate_docpairs')}
</div>
''')
        if dataset.has_qlogs():
            parent_ds = ir_datasets.qlogs_parent_id(dataset_id)
            parent_ds_note = ''
            if parent_ds != dataset_id:
                parent_ds_note = f'<p>Inherits qlogs from <a class="ds-ref">{parent_ds}</a></p>'
            out.write(f'''
<a class="tab" target="{dataset_id}__qlogs">qlogs</a>
<div id="{dataset_id}__qlogs" class="tab-content">
{ds_page_count(dataset, dataset_id, "qlogs")}
{parent_ds_note}
<div>Query Log type:</div>
{generate_data_format(dataset.qlogs_cls())}
{generate_examples(generators, 'generate_qlogs')}
</div>
''')
        if 'bibtex_ids' in documentation:
            prefix = f'<p><a href="ir_datasets.bib">ir_datasets.bib</a>:</p><cite class="select">\\cite{{{",".join(documentation["bibtex_ids"])}}}</cite>'
            bibtex = '\n'.join(bibliography[bid] for bid in documentation['bibtex_ids'])
            out.write(f'''
<a class="tab" target="{dataset_id}__citation">Citation</a>
<div id="{dataset_id}__citation" class="tab-content">
{prefix}
<p>Bibtex:</p>
<cite class="select">{bibtex}</cite>
</div>
''')
        metadata = dataset.metadata()
        if metadata:
            out.write(f'''
<a class="tab" target="{dataset_id}__metadata">Metadata</a>
<div id="{dataset_id}__metadata" class="tab-content">
<pre class="metadata">{json.dumps(dataset.metadata(), indent=2)}</pre>
</div>
''')
        out.write('</div>')
        out.seek(0)
        return out.read()

def generate_examples(generators, fn):
    from pygments import highlight
    from pygments.lexers import PythonLexer, BashLexer
    from pygments.formatters import HtmlFormatter
    with io.StringIO() as f:
        f.write('<p>Examples:</p>')
        f.write('<div class="ex-tabs">')
        for (name, kwd), generator in generators.items():
            f.write(f'''
<a class="ex-tab" target="{kwd}">{name}</a>
<div class="ex-tab-content {kwd}">
''')
            example = getattr(generator, fn)()
            if example is None:
                f.write(f'<p><i>No example available for {name}</i></p>')
            else:
                if example.code:
                    lexer = {
                        'py': PythonLexer,
                        'bash': BashLexer,
                    }[example.code_lang]()
                    code = highlight(example.code, lexer, HtmlFormatter())
                    f.write(code)
                if example.output:
                    f.write(f'''
<code class="output">
{example.output}
</code>
''')
                if example.message_html:
                    f.write(f'<p>{example.message_html}</p>')
            f.write('</div>')
        f.write('</div>')
        f.seek(0)
        return f.read()


def generate_data_access_section(documentation):
    if 'data_access' not in documentation:
        return ''
    return f'''
<div id="DataAccess">
<h3>Data Access Information</h3>
{documentation["data_access"]}
</div>
'''


def generate_data_format(cls):
    if cls in (str, int, float, bytes, bool):
        return f'<span class="kwd">{cls.__name__}</span>'
    if cls in (datetime.datetime,):
        return f'<span class="kwd"><a href="https://docs.python.org/3/library/datetime.html#datetime.datetime">datetime</a></span>'
    if cls == type(None):
        return f'<span class="kwd">None</span>'
    elif isinstance(cls, typing._GenericAlias):
        args = []
        for arg in cls.__args__:
            if arg is Ellipsis:
                args.append(' ...')
            else:
                args.append(generate_data_format(arg))
        if cls._name in ('Tuple', 'List', 'Dict'):
            return f'<span class="kwd">{cls._name}</span>[{",".join(args)}]'
        if cls._name is None: # aka union
            if len(args) == 2 and args[1] == '<span class="kwd">None</span>':
                return f'<span class="kwd">Optional</span>[{args[0]}]'
            else:
                return f'<span class="kwd">Union</span>[{",".join(args)}]'
    elif tuple in cls.__bases__ and hasattr(cls, '_fields'):
        fields = []
        for i, field in enumerate(cls._fields):
            f_type = 'UNKNOWN'
            if hasattr(cls, '__annotations__'):
                f_type = generate_data_format(cls.__annotations__[field])
            fields.append(f'<li data-tuple-idx="{i}"><span class="">{field}</span>: {f_type}</li>')
        return f"""
<div class="type">
<div class="type-name">{cls.__name__}: (<span class="kwd">namedtuple</span>)</div>
<ol class="type-fields">
{"".join(fields)}
</ol>
</div>""".strip()
    elif Enum in cls.__bases__:
        fields = list(cls.__members__)
        return f'<span class="kwd">{cls.__name__}</span>[{", ".join(fields)}]'
    raise RuntimeError(f"uknown class {cls}")





def generate_index(out_dir, version, top_level_map):
    with page_template('index.html', out_dir, version, title='Catalog') as out:
        if version == 'master':
            install = '--upgrade git+https://github.com/allenai/ir_datasets.git'
        elif version.startswith('v'):
            install = f'ir_datasets=={version[1:]}'
        elif not version:
            install = '--upgrade ir_datasets'
        else:
            raise RuntimeError(f'unknown version {version}')
        index = []
        jump = []
        deprecated = []
        for top_level in sorted(top_level_map):
            names = [top_level] + sorted(x[0] for x in top_level_map[top_level])
            for name in names:
                dataset = ir_datasets.registry[name]
                parent = name.split('/')[0]
                if hasattr(dataset, 'deprecated'):
                    deprecated.append((name, parent, dataset))
                    continue
                if parent != name:
                    ds_name = f'<a href="{parent}.html#{name}"><kbd><span class="prefix"><span class="screen-small-hide">{parent}</span><span class="screen-small-show">&hellip;</span></span>{name[len(parent):]}</kbd></a>'
                    tbody = ''
                    row_id = ''
                else:
                    ds_name = f'<a style="font-weight: bold;" href="{parent}.html"><kbd>{parent}</kbd></a></li>'
                    tbody = '</tbody><tbody>'
                    row_id = f' id="{parent}"'
                    jump.append(f'<option value="{parent}">{parent}</option>')
                index.append(f'{tbody}<tr{row_id}><td>{ds_name}</td><td id="{name}-docs" class="center">{emoji(dataset, name, "docs", parent)}</td><td id="{name}-queries" class="center">{emoji(dataset, name, "queries", parent)}</td><td id="{name}-qrels" class="center">{emoji(dataset, name, "qrels", parent)}</td><td id="{name}-scoreddocs" class="center screen-small-hide">{emoji(dataset, name, "scoreddocs", parent)}</td><td id="{name}-docpairs" class="center screen-small-hide">{emoji(dataset, name, "docpairs", parent)}</td><td id="{name}-qlogs" class="center screen-small-hide">{emoji(dataset, name, "qlogs", parent)}</td></tr>')
        index = '\n'.join(index)
        jump = '\n'.join(jump)
        out.write(f'''
<p>
<code>ir_datasets</code> provides a common interface to many IR ranking datasets.
</p>

<h2 class="underline">Getting Started</h2>

<p>
Install with pip:
</p>

<code class="example">pip install {install}</code>

<p>Guides:</p>

<ul>
<li>Colab Tutorials: <a href="https://colab.research.google.com/github/allenai/ir_datasets/blob/master/examples/ir_datasets.ipynb">python</a>, <a href="https://colab.research.google.com/github/allenai/ir_datasets/blob/master/examples/ir_datasets_cli.ipynb">CLI</a></li>
<li><a href="python.html">Python API Documentation</a> (<a href="python-beta.html">beta version</a>)</li>
<li><a href="cli.html">CLI Documentation</a></li>
<li><a href="downloads.html">Download Dashboard</a></li>
<li><a href="counts.html">Dataset Counts</a></li>
<li><a href="https://github.com/allenai/ir_datasets/blob/master/examples/adding_datasets.ipynb">Adding new datasets</a></li>
<li><a href="https://arxiv.org/pdf/2103.02280.pdf">ir_datasets SIGIR resource paper</a></li>
<li>Using <kbd>ir_datasets</kbd> with&hellip;
<a href="pyterrier.html">PyTerrier</a> &middot;
<a href="ir-measures.html">ir-measures</a> &middot;
<a href="trec_eval.html">trec_eval</a> &middot;
<a href="experimaestro.html">Experimaestro</a>
</li>
<li><a href="design.html">Design Documentation</a></li>
</ul>

<h2 class="underline" style="margin-bottom: 4px;">Dataset Index</h2>
<select id="DatasetJump">
<option value="">Jump to Dataset...</option>
{jump}
</select>
<p>✅: Data available as automatic download</p>
<p>⚠️: Data available from a third party</p>
<p>⬆️: Data inherited from a parent dataset (highlights which one on hover)</p>
<table>
<tbody>
<tr>
<th class="stick-top">Dataset</th>
<th class="stick-top">docs</th>
<th class="stick-top">queries</th>
<th class="stick-top">qrels</th>
<th class="stick-top screen-small-hide">scoreddocs</th>
<th class="stick-top screen-small-hide">docpairs</th>
<th class="stick-top screen-small-hide">qlogs</th>
</tr>
{index}
</tbody>
</table>
''')
        deprecated_html = ', '.join([f'<a href="{parent}.html#{name}"><kbd>{name}</kbd></a>' for name, parent, dataset in deprecated])
        out.write(f'''
<h2 class="underline">Deprecated</h2>
<p>These datasets have been deprecated. We keep them in the package for reproducibility, but
better alternative dataset IDs exist (e.g., with improved corpus parsing).</p>
<p>
{deprecated_html}
</p>
''')
        v_prefix = '../' if version else ''
        versions = [str(v).split('/')[-2] for v in sorted(Path(out_dir).glob('*/index.html'))]
        versions = [v for v in versions if v != version]
        versions = [f'<li><a href="{v_prefix}{v}/index.html">{v}</a></li>' for v in versions]
        if version:
            versions = [f'<li><a href="../index.html">Latest Release</a></li>'] + versions
        versions = '\n'.join(versions)
        out.write(f'''
<h2 class="underline">Other Versions</h2>
<ul>
{versions}
</ul>
<h2 class="underline">Citation</h2>
<p>
When using datasets provided by this package, be sure to properly cite them. Bibtex for each dataset
can be found on each dataset's documenation page.
</p>
<p>If you use this tool, please cite our <a href="https://arxiv.org/pdf/2103.02280.pdf">SIGIR resource paper</a>:</p>
<cite class="select">@inproceedings{{macavaney:sigir2021-irds,
  author = {{MacAvaney, Sean and Yates, Andrew and Feldman, Sergey and Downey, Doug and Cohan, Arman and Goharian, Nazli}},
  title = {{Simplified Data Wrangling with ir_datasets}},
  year = {{2021}},
  booktitle = {{SIGIR}}
}}
</cite>
''')


def generate_counts(out_dir, version, top_level_map):
    with page_template('counts.html', out_dir, version, title='Counts') as out, open(get_file_path(out_dir, version, 'counts.csv'), 'wt') as csv_out:
        index = []
        csv_out.write(f'Dataset,docs,queries,qrels,qrels/q,scoreddocs,scoreddocs/q,docpairs,docpairs/q,qlogs\n')
        json_out = {}
        for top_level in sorted(top_level_map):
            names = [top_level] + sorted(x[0] for x in top_level_map[top_level])
            for name in names:
                dataset = ir_datasets.registry[name]
                parent = name.split('/')[0]
                if parent != name:
                    ds_name = f'<a href="{parent}.html#{name}"><kbd><span class="prefix"><span class="screen-small-hide">{parent}</span><span class="screen-small-show">&hellip;</span></span>{name[len(parent):]}</kbd></a>'
                    tbody = ''
                    row_id = ''
                else:
                    ds_name = f'<a style="font-weight: bold;" href="{parent}.html"><kbd>{parent}</kbd></a></li>'
                    tbody = '</tbody><tbody>'
                    row_id = f' id="{parent}"'
                index.append(f'''{tbody}<tr{row_id}>
<td>{ds_name}</td>
<td id="{name}-docs" class="right">{ds_counts(dataset, name, "docs")}</td>
<td id="{name}-queries" class="right">{ds_counts(dataset, name, "queries")}</td>
<td id="{name}-qrels" class="right">{ds_counts(dataset, name, "qrels")}</td>
<td id="{name}-qrels-q" class="right">{ds_per_q_count(dataset, name, 'qrels')}</td>
<td id="{name}-scoreddocs" class="right">{ds_counts(dataset, name, "scoreddocs")}</td>
<td id="{name}-scoreddocs-q" class="right">{ds_per_q_count(dataset, name, "scoreddocs")}</td>
<td id="{name}-docpairs" class="right">{ds_counts(dataset, name, "docpairs")}</td>
<td id="{name}-docpairs-q" class="right">{ds_per_q_count(dataset, name, "docpairs")}</td>
<td id="{name}-qlogs" class="right">{ds_counts(dataset, name, "qlogs")}</td>
</tr>''')
                csv_out.write(f'{name},{ds_count_value(dataset, name, "docs") or ""},{ds_count_value(dataset, name, "queries") or ""},{ds_count_value(dataset, name, "qrels") or ""},{ds_per_q_count_value(dataset, name, "qrels") or ""},{ds_count_value(dataset, name, "scoreddocs") or ""},{ds_per_q_count_value(dataset, name, "scoreddocs") or ""},{ds_count_value(dataset, name, "docpairs") or ""},{ds_per_q_count_value(dataset, name, "docpairs") or ""},{ds_count_value(dataset, name, "qlogs") or ""}\n')
                json_out[name] = {
                    'docs_count': ds_count_value(dataset, name, "docs"),
                    'queries_count': ds_count_value(dataset, name, "queries"),
                    'qrels_count': ds_count_value(dataset, name, "qrels"),
                    'qrels_per_query': ds_per_q_count_value(dataset, name, "qrels"),
                    'scoreddocs_count': ds_count_value(dataset, name, "scoreddocs"),
                    'scoreddocs_per_query': ds_per_q_count_value(dataset, name, "scoreddocs"),
                    'docpairs_count': ds_count_value(dataset, name, "docpairs"),
                    'docpairs_per_query': ds_per_q_count_value(dataset, name, "docpairs"),
                    'qlogs_count': ds_count_value(dataset, name, "qlogs"),
                }
        index = '\n'.join(index)
        out.write(f'''
<p>Other formats: <a href="counts.csv">CSV</a>, <a href="counts.json">JSON</a></p>
<p><input type="radio" id="Approx" name="counts" value="Approx" checked><label for="Approx">Approx. counts</label> <input type="radio" id="Exact" name="counts" value="Exact"><label for="Exact">Exact counts</label></p>
<p>K: Thousand (&times;1,000)</p>
<p>M: Million (&times;1,000,000)</p>
<p>B: Billion (&times;1,000,000,000)</p>
<p>/q: Per query (value divided by query count)</p>
<p>Hover over number for exact count.</p>
<table>
<tbody>
<tr>
<th class="stick-top">Dataset</th>
<th class="stick-top">docs</th>
<th class="stick-top">queries</th>
<th class="stick-top">qrels</th>
<th class="stick-top">/q</th>
<th class="stick-top">scoreddocs</th>
<th class="stick-top">/q</th>
<th class="stick-top">docpairs</th>
<th class="stick-top">/q</th>
<th class="stick-top">qlogs</th>
</tr>
{index}
</tbody>
</table>
<script type="text/javascript">
''')
        out.write(r'''
$(function () {
    $('kbd[title]').each(function (i, e) {
        var $e = $(e);
        $e.attr('data-approx', $e.text());
        $e.attr('data-exact', $e.attr('title'));
    });
    $(document).on('change', '[name=counts]', function (e) {
        var $target = $(e.target);
        if (!$target.prop('checked')) {
            return;
        }
        if ($target.attr('id') == 'Exact') {
            $('kbd[title]').each(function (i, e) {
                var $e = $(e);
                $e.text($e.attr('data-exact'));
                $e.attr('title', $e.attr('data-approx'));
            });
        } else if ($target.attr('id') == 'Approx') {
            $('kbd[title]').each(function (i, e) {
                var $e = $(e);
                $e.text($e.attr('data-approx'));
                $e.attr('title', $e.attr('data-exact'));
            });
        }
    });
});
</script>
''')
    with open(get_file_path(out_dir, version, 'counts.json'), 'wt') as fjson:
        json.dump(json_out, fjson)






def generate_redirect(out_dir, version, page_from, page_to):
    with open(get_file_path(out_dir, version, page_from), 'wt') as out:
        out.write(f'''
<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="refresh" content="0; URL={page_to}" />
  <title>ir_datasets</title>
</head>
<body>
  <p>Redirecting <a href="{page_to}">here</a></p>
</body>
</html>
''')




def generate_python_docs(out_dir, version):
    template = Template(filename=os.path.join("templates", "python.html"))
    with page_template('python.html', out_dir, version, title='Python API') as out:
        out.write(template.render())

    template = Template(filename=os.path.join("templates", "python-beta.html"))
    with page_template('python-beta.html', out_dir, version, title='Beta Python API') as out:
        out.write(template.render())


def generate_cli_docs(out_dir, version):
    template = Template(filename=os.path.join("templates", "cli.html"))
    with page_template('cli.html', out_dir, version, title='Command Line Interface') as out:
        out.write(template.render())


def generate_downloads(out_dir, version):
    template = Template(filename=os.path.join("templates", "downloads.html"))
    with page_template('downloads.html', out_dir, version, title='Download dashboard') as out:
        out.write(template.render())


def generate_integrations(out_dir, version):
    from pygments import highlight
    from pygments.lexers import PythonLexer, BashLexer
    from pygments.formatters import HtmlFormatter

    def hl(c):
        return highlight(c, PythonLexer(), HtmlFormatter())

    def hlb(c):
        return highlight(c, BashLexer(), HtmlFormatter())

    template = Template(filename=os.path.join("templates", "pyterrier.html"))
    with page_template('pyterrier.html', out_dir, version, title='PyTerrier &amp; ir_datasets', include_irds_title=False) as out:
        out.write(template.render(hl=hl))
    template = Template(filename=os.path.join("templates", "ir-measures.html"))
    with page_template('ir-measures.html', out_dir, version, title='ir_measures &amp; ir_datasets', include_irds_title=False) as out:
        out.write(template.render(hl=hl, hlb=hlb))
    template = Template(filename=os.path.join("templates", "trec_eval.html"))
    with page_template('trec_eval.html', out_dir, version, title='trec_eval &amp; ir_datasets', include_irds_title=False) as out:
        out.write(template.render(hl=hl, hlb=hlb))
    template = Template(filename=os.path.join("templates", "design.html"))
    with page_template('design.html', out_dir, version, title='Design', include_irds_title=True) as out:
        out.write(template.render(hl=hl))
    template = Template(filename=os.path.join("templates", "experimaestro.html"))
    with page_template('experimaestro.html', out_dir, version, title='Experimaestro', include_irds_title=True) as out:
        out.write(template.render(hl=hl))


@contextmanager
def page_template(file, base_dir, version, title=None, source=None, include_irds_title=True):
    with open(get_file_path(base_dir, version, file), 'wt') as out:
        no_index = '<meta name="robots" content="noindex,nofollow" />' if version else ''
        out.write(f'''<!DOCTYPE html>
<html>
<head>
<link rel="stylesheet" href="main.css" />
<script src="https://code.jquery.com/jquery-1.12.4.min.js" integrity="sha256-ZosEbRLbNQzLpnKIkEdrPv7lOy9C27hHQ+Xp8a4MxAQ=" crossorigin="anonymous"></script>
<script src="https://code.jquery.com/ui/1.12.1/jquery-ui.min.js" integrity="sha256-VazP97ZCwtekAsvgPBSUwPFKdrwD3unUfSGVYrahUqU=" crossorigin="anonymous"></script>
<script src="main.js"></script>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
{no_index}
<title>{(title + ' - ir_datasets' if include_irds_title else title) if title else 'ir_datasets'}</title>
</head>
<body>
<div class="page">
''')
        path_segment = 'blob' if source else 'tree'
        url = 'https://github.com/allenai/ir_datasets/' + (f'{path_segment}/{version or ("v" + ir_datasets.__version__)}/' if source else '') + (f'ir_datasets/{source}' if source else '')
        text = source or 'allenai/ir_datasets'
        if version: # a specific version -- warn the user
            out.write(f'''
<div class="banner">This documentation is for <strong>{version}</strong>. See <a href="../{file}">here</a> for documentation of the current latest version on pypi.</div>
''')
        if file != 'index.html':
            out.write(f'''
<div style="position: absolute; top: 4px; left: 4px;"><a href="index.html">&larr; home</a></div>
''')
        out.write(f'''
<div style="position: absolute; top: 4px; right: 4px;">Github: <a href="{url}">{text}</a></div>
''')
        if include_irds_title:
            out.write(f'<h1><code>ir_datasets</code>{": " + title if title else ""}</h1>')
        else:
            out.write(f'<h1>{title}</h1>')
        yield out
        out.write(f'''
</div>
</body>
</html>
''')


def generate_css(base_dir, version):
    with open(get_file_path(base_dir, version, 'main.css'), 'wt') as out:
        out.write(open('templates/main.css').read())


def generate_js(base_dir, version):
    with open(get_file_path(base_dir, version, 'main.js'), 'wt') as out:
        out.write(open('templates/main.js').read())


def generate_bib(base_dir, version):
    with open(get_file_path(base_dir, version, 'ir_datasets.bib'), 'wb') as out:
        out.write(pkgutil.get_data('ir_datasets', 'docs/bibliography.bib'))


def generate_github_action(top_levels):
    top_levels = sorted(list(top_levels) + ['touche']) # TODO: why is touche split out?
    no_delay = {'antique', 'aol-ia', 'argsme', 'beir', 'clirmatrix', 'codesearchnet', 'cranfield', 'dpr-w100', 'hc4', 'highwire', 'lotte', 'medline', 'mmarco', 'mr-tydi', 'msmarco-qna', 'natural-questions', 'nfcorpus', 'touche', 'tripclick', 'vaswani', 'wikir'}
    with open('.github/workflows/verify_downloads.yml', 'wt') as out:
        out.write(f'''name: Downloadable Content

on:
  schedule:
    - cron: '0 8 * * 0' # run every sunday at (around) 8:00am UTC
  workflow_dispatch:
    inputs:
      dataset:
        description: "Top-level dataset ID to run (or leave blank for all)" 
        required: false
        default: ''

jobs:

  create_branch:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - run: git checkout -b verify-downloads-${{{{github.run_number}}}} --track
    - run: 'echo ${{{{github.run_number}}}} > docs/dlc/_placeholder.txt'
    - uses: EndBug/add-and-commit@v8
      with:
        add: 'docs/dlc/_placeholder.txt'
        message: 'touch'
        author_name: GitHub Actions
        author_email: actions@github.com




''')
        for dsid in top_levels:
            out.write(f'''
  {dsid}:
    if: "!github.event.inputs.dataset || github.event.inputs.dataset == '{dsid}'"
    needs: [create_branch]
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
      with:
        repository: allenai/ir_datasets
        path: ir-datasets
    - uses: actions/checkout@v2
      with:
        path: ir-datasets.com
        ref: verify-downloads-${{{{github.run_number}}}}
    - uses: actions/setup-python@v2
      with:
        python-version: '3.x'
    - name: Install dependencies
      run: |
        cd ir-datasets
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Test
      env:
        IR_DATASETS_DL_DISABLE_PBAR: 'true'
      run: |
        cd ir-datasets
        python -m test.downloads --filter "^{dsid}/" --output download.new.json{"" if dsid in no_delay else " --randdelay 60"}
    - name: Upload
      if: always()
      run: |
        cd ir-datasets
        python ../ir-datasets.com/merge_history.py download.new.json "../ir-datasets.com/docs/dlc/{dsid}.json"
        cd ../ir-datasets.com/
        git config user.email "actions@github.com"
        git config user.name "GitHub Actions"
        git pull --rebase --autostash
        git add docs/dlc/*.json
        git commit -m 'verify_downloads: {dsid}'
        if git push ; then
          echo success
        else
          # Try again...
          git pull --rebase --autostash
          git push
        fi''')
        out.write(f'''
  merge_dlc:
    if: ${{{{ always() }}}}
    needs: [{', '.join(top_levels)}]
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
      with:
        ref: verify-downloads-${{{{github.run_number}}}}
        fetch-depth: 0
    - uses: actions/setup-python@v2
      with:
        python-version: '3.x'
    - run: |
        git config user.email "actions@github.com"
        git config user.name "GitHub Actions"
        python merge_dlc.py
    - uses: EndBug/add-and-commit@v8
      with:
        add: 'docs/dlc/*.json'
        message: 'from verify_downloads'
        author_name: GitHub Actions
        author_email: actions@github.com
    - run: |
        git checkout master
        git merge -s recursive -Xtheirs --squash verify-downloads-${{{{github.run_number}}}} --allow-unrelated-histories
        git commit -m verify-downloads-${{{{github.run_number}}}}
        git push origin master
        git push origin --delete verify-downloads-${{{{github.run_number}}}}
''')


    with open('.github/workflows/head_downloads.yml', 'wt') as out:
        out.write(f'''name: Downloadable Content, HEAD

on:
  schedule:
    - cron: '0 8 * * 1-6' # run every day except sunday at (around) 8:00am UTC
  workflow_dispatch:
    inputs:
      dataset:
        description: "Top-level dataset ID to run (or leave blank for all)" 
        required: false
        default: ''

jobs:

  create_branch:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - run: git checkout -b head-downloads-${{{{github.run_number}}}} --track
    - run: 'echo ${{{{github.run_number}}}} > docs/dlc/_placeholder.txt'
    - uses: EndBug/add-and-commit@v8
      with:
        add: 'docs/dlc/_placeholder.txt'
        message: 'touch'
        author_name: GitHub Actions
        author_email: actions@github.com




''')
        for dsid in top_levels:
            out.write(f'''
  {dsid}:
    if: "!github.event.inputs.dataset || github.event.inputs.dataset == '{dsid}'"
    needs: [create_branch]
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
      with:
        repository: allenai/ir_datasets
        path: ir-datasets
    - uses: actions/checkout@v2
      with:
        path: ir-datasets.com
        ref: head-downloads-${{{{github.run_number}}}}
    - uses: actions/setup-python@v2
      with:
        python-version: '3.x'
    - name: Install dependencies
      run: |
        cd ir-datasets
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Test
      env:
        IR_DATASETS_DL_DISABLE_PBAR: 'true'
      run: |
        cd ir-datasets
        python -m test.downloads --head_precheck --filter "^{dsid}/" --output download.new.json --randdelay 10
    - name: Upload
      if: always()
      run: |
        cd ir-datasets
        python ../ir-datasets.com/merge_history.py download.new.json "../ir-datasets.com/docs/dlc/{dsid}.json"
        cd ../ir-datasets.com/
        git config user.email "actions@github.com"
        git config user.name "GitHub Actions"
        git pull --rebase --autostash
        git add docs/dlc/*.json
        git commit -m 'head_downloads: {dsid}'
        until git push
        do
          echo trying again
          git pull --rebase --autostash
        done
        echo success
''')
        out.write(f'''
  merge_dlc:
    if: ${{{{ always() }}}}
    needs: [{', '.join(top_levels)}]
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
      with:
        ref: head-downloads-${{{{github.run_number}}}}
        fetch-depth: 0
    - uses: actions/setup-python@v2
      with:
        python-version: '3.x'
    - run: |
        git config user.email "actions@github.com"
        git config user.name "GitHub Actions"
        python merge_dlc.py
    - uses: EndBug/add-and-commit@v8
      with:
        add: 'docs/dlc/*.json'
        message: 'from head_downloads'
        author_name: GitHub Actions
        author_email: actions@github.com
    - run: |
        git checkout master
        git merge -s recursive -Xtheirs --squash head-downloads-${{{{github.run_number}}}} --allow-unrelated-histories
        git commit -m head-downloads-${{{{github.run_number}}}}
        git push origin master
        git push origin --delete head-downloads-${{{{github.run_number}}}}
''')


def get_file_path(base_dir, version, file):
    return f'{base_dir}/{version}/{file}' if version else f'{base_dir}/{file}'


def generate_qrel_defs_table(dataset):
    defs = dataset.qrels_defs()
    metadata = dataset.qrels_metadata()
    counts_by_relevance = metadata.get('fields', {}).get('relevance', {}).get('counts_by_value')
    rows = []
    for score, desc in sorted(defs.items()):
        if counts_by_relevance:
            c = counts_by_relevance.get(str(score), 0)
            count = f'<td class="right">{format_count(c)}</td><td class="right">{c/sum(counts_by_relevance.values())*100:0.1f}%</td>'
        else:
            count = ''
        rows.append(f'<tr><td class="relScore">{score}</td><td>{desc}</td>{count}</tr>')
    rows = "\n".join(rows)
    if counts_by_relevance:
        count = f'<th>Count</th><th>%</th>'
    else:
        count = ''
    return f'''
<table>
<tr><th>Rel.</th><th>Definition</th>{count}</tr>
{rows}
</table>
'''

def emoji(ds, dsid, arg, top_level):
    has = getattr(ds, f'has_{arg}')()
    if has:
        parent = getattr(ir_datasets, f'{arg}_parent_id')(dsid)
        if parent != dsid:
            return f'<span style="cursor: help;" title="{arg} inherited from {parent}" data-highlight="{parent}-{arg}">⬆️</span>'
        else:
            instructions = hasattr(ds, f'documentation') and ds.documentation().get(f'{arg}_instructions')
            if instructions:
                return f'<a href="{top_level}.html#DataAccess" title="{instructions}. Click for details.">⚠️</a>'
            return f'<span style="cursor: help;" title="{arg} available as automatic download">✅</span>'
    return ''


def format_count(count, pad=True):
    display_count = count
    formats = [
        ('{:.0f}<span style="visibility: hidden;">&nbsp;</span>' if pad else '{:.0f}', 1),
        ('{:.0f}<span style="visibility: hidden;">&nbsp;</span>' if pad else '{:.0f}', 10),
        ('{:.0f}<span style="visibility: hidden;">&nbsp;</span>' if pad else '{:.0f}', 100),
        ('{:.1f}K', 1), ('{:.0f}K', 10), ('{:.0f}K', 100),
        ('{:.1f}M', 1), ('{:.0f}M', 10), ('{:.0f}M', 100),
        ('{:.1f}B', 1), ('{:.0f}B', 10), ('{:.0f}B', 100),
    ]
    while display_count >= 10:
        display_count = display_count / 10
        formats.pop(0)
    return f'<kbd title="{count}">{formats[0][0].format(display_count*formats[0][1])}</kbd>'

def ds_count_value(ds, dsid, etype):
    has = getattr(ds, f'has_{etype}')()
    if has:
        metadata = getattr(ds, f'{etype}_metadata')()
        if 'count' in metadata:
            return metadata['count']

def ds_counts(ds, dsid, etype):
    has = getattr(ds, f'has_{etype}')()
    if has:
        count = ds_count_value(ds, dsid, etype)
        if count is not None:
            return format_count(count)
        else:
            return f'<span title="has {etype} but missing metadata">⚠️</span>'
    return ''

def ds_page_count(ds, dsid, etype):
    has = getattr(ds, f'has_{etype}')()
    if has:
        count = ds_count_value(ds, dsid, etype)
        if count is not None:
            return f'<span class="ds-count">{format_count(count, pad=False)} <kbd>{etype}</kbd></span>'
    return ''

def ds_per_q_count_value(ds, dsid, etype):
    has = getattr(ds, f'has_{etype}')() and ds.has_queries()
    if has:
        metadata_qrels = getattr(ds, f'{etype}_metadata')()
        metadata_queries = ds.queries_metadata()
        if 'count' in metadata_qrels and 'count' in metadata_queries:
            count = metadata_qrels['count'] / metadata_queries['count']
            return count

def ds_per_q_count(ds, dsid, etype):
    count = ds_per_q_count_value(ds, dsid, etype)
    if count is not None:
        return f'<kbd title="{count:0.4f}">{count:0.1f}</kdb>'
    return ''


def _lang(lang_code):
    if lang_code is None:
        return '<em>multiple/other/unknown</em>'
    return f'<span class="lang-code">{lang_code}</span>'


if __name__ == '__main__':
    main()
