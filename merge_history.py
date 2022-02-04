import os
import argparse
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('new_file')
    parser.add_argument('target_file')
    args = parser.parse_args()
    with open(args.new_file) as fin:
        new = json.load(fin)
    if os.path.exists(args.target_file):
        with open(args.target_file) as fin:
            target = json.load(fin)
    else:
        target = []
    target_id2idx = {t['name']: i for i, t in enumerate(target)}
    for rec in new:
        rec['recent_history'] = [{'result': rec['result'], 'time': rec['time']}]
        if rec['name'] in target_id2idx:
            rec['recent_history'] = target[target_id2idx[rec['name']]].get('recent_history', []) + rec['recent_history']
            rec['recent_history'] = rec['recent_history'][-16:]
            target[target_id2idx[rec['name']]] = rec
        else:
            target.append(rec)

    with open(args.target_file, 'wt') as fout:
        json.dump(target, fout)


if __name__ == '__main__':
    main()
