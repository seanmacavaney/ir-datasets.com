from glob import glob
import json

def main():
    with open('docs/dlc/dlc_merged.json', 'rt') as fin:
        merged = json.load(fin)

    with open('docs/dlc/dlc_history.json', 'rt') as fin:
        history = json.load(fin)

    for file in glob('docs/dlc/*.json'):
        name = file.split('/')[-1].replace('.json', '')
        if name.startswith('dlc_'): # dlc_merged.json and dlc_history.json
            continue
        with open(file, 'rt') as fin:
            data = json.load(fin)
            data_by_name = {d['name']: d for d in data}
            merged_tmp = merged.setdefault(name, [])
            for record in merged_tmp:
                if record['name'] in data_by_name:
                    record.update(data_by_name[record['name']])
                    del data_by_name[record['name']]
            for record in data_by_name.values():
                merged_tmp.append(record)
            history.setdefault(name, {})
            for record in data:
                new_rec = dict(record)
                del new_rec['name']
                if 'recent_history' in new_rec:
                    del new_rec['recent_history']
                history_tmp = history[name].setdefault(record['name'], [])
                if not history_tmp or history_tmp[-1]['time'] != new_rec['time']:
                    history_tmp.append(new_rec)

    with open('docs/dlc/dlc_merged.json', 'wt') as fout:
        json.dump(merged, fout)

    with open('docs/dlc/dlc_history.json', 'wt') as fout:
        json.dump(history, fout)


if __name__ == '__main__':
    main()
