#!/usr/bin/python2.7

from savingCalculator.TeevityAPI import TeevityAPI
from savingCalculator.SavingCalculator import SavingCalculator
from dateutil.parser import *
from datetime import *
import json
import sys
import argparse

def parse_filter_opt(opt, filterType, out):
    for cur in opt:
        split = cur.split(':')
        if len(split) < 2:
            return False   
        fields = split[1].split(',')
        if split[0] not in out:
            out[split[0]] = {filterType: fields}
        else:
            out[split[0]][filterType] = fields

    return True

def merge_rows(datas, mergeBy):
    first = False
    for v in datas:
        if first is False:
            first = v
            if len(mergeBy) < 1:
                return first
        else:
            for key in mergeBy:
                first[key] += v[key]
    return first

def group_rows(datas, groupBy, mergeBy):
    lastGroupLvls = []
    result = {}
    for row in datas:
        cur = result
        groupByLen = len(groupBy)
        i = 0
        while i < (groupByLen - 1):
            keyValue = row[groupBy[i]]
            if keyValue not in cur:
                cur[keyValue] = {}
                # Last level for this new group : store it  
                if (i + 1) == (groupByLen - 1):
                    lastGroupLvls.append(cur[keyValue])                
            cur = cur[keyValue]
            i += 1
        lastKey = row[groupBy[i]]
        if lastKey not in cur:
            cur[lastKey] = []
        # cur[lastKey] is now the list containing all rows of same group than current row
        cur[lastKey].append(row)

    if len(groupBy) == 1:
        lastGroupLvls = [result]
    if mergeBy is not None and len(mergeBy) > 0:
        for curLastLvl in lastGroupLvls:
            for grpKey in curLastLvl:
                merged = merge_rows(curLastLvl[grpKey], mergeBy)
                curLastLvl[grpKey] = merged

    return result

def apply_filters(datas, filters):
    if filters['group_by'] is not None:
        return group_rows(datas, filters['group_by'], filters['merge_by'] if 'merge_by' in filters else None)
    if filters['merge_by'] is not None:
        return merge_rows(datas, filters['merge_by'])
    return datas

def run(args, filters=False):
    if 'costs_filepath' not in args or 'events_filepath' not in args:
        args['costs_filepath'] = "./dataMocks/csv/generated_costs.csv"
        args['events_filepath'] = "./dataMocks/csv/generated_events.csv"

    # filters preset
    if 'filters_preset' in args:
        if 'sum_by_hour' in args['filters_preset']:
            if filters is False:
                filters = {}
            filters['savings'] = {'group_by': ['date', 'type'], 'merge_by': ['saving', 'depth']}
            filters['costs'] = {'group_by': ['date'], 'merge_by': ['cost', 'saving']}
        if 'sum_by_cau' in args['filters_preset']:
            if filters is False:
                filters = {}
            filters['savingCycles'] = {'group_by': ['type', 'CAU']}

    api = TeevityAPI(args['costs_filepath'], args['events_filepath'])
    calculator = SavingCalculator(api.GetCostDatas(), api.GetEvents())
    out = {}
    try:
        raw = calculator.getSavings()
    except Exception as error:
         sys.stderr.write("An error occured %s\n" % (error))
         return (-1)
    except KeyboardInterrupt:
         sys.stderr.write("\nSIGINT caught, interrupt program\n")
         return (-1)
    except:
         sys.stderr.write("Unknown error occured\n")
         return (-1)
    
    out['dates'] = raw['dates']
    raw.pop('dates')
    if filters is not False:
        out['summarize'] = {}
        for field in filters:
            out['summarize'][field] = apply_filters(raw[field], filters[field])
    if 'no_raw_fields' not in args or args['no_raw_fields'] is False:
        out['raw'] = raw
        if 'only_raw_fields' in args and args['only_raw_fields'] is not None:
            only_fields = args['only_raw_fields'].split(',')
            skip = list(filter(lambda k: k not in only_fields, raw.keys()))
            for k in skip:
                raw.pop(k)

    if 'output_file' not in args or args['output_file'] is None:
        print(json.dumps(out))
    else:
        calculator.storeToFile(out, args['output_file'])
    return 0

def main():
    parser = argparse.ArgumentParser(
        "Provided cloud cost & event datas, compute then output in 3 fields of json 'raw' result : savings, savingCycles, costs, eventNames. \n "
        "GROUP_BY and MERGE_BY options need to start by one of these 3 fields followed by ':' in order to filter on the right field. \n "
        "ex: ./calcSavings --group-by=savings:date,type --merge-by=savings:saving,depth \t #Group savings by unique date then event type, before merging all of their saving in one row\n")
    parser.add_argument("--group-by", type=str, action="append", help="Group saving datas by some columns of given fieldname. Output result in 'summarize'")
    parser.add_argument("--merge-by", type=str, action="append", help="Merge saving datas by some columns of given fieldname. Output result in 'summarize'")
    parser.add_argument("--no-raw-fields", action="store_true", help="Disable output of whole datas set computed by the algorithm in 'raw' field.")
    parser.add_argument("--only-raw-fields", type=str, help="Output only raw fields indicated by this option")
    parser.add_argument("--sum-by-hour", action="store_true", help="Same as --group-by=savings:date,type --merge-by=savings:saving,depth --group-by=costs:date --merge-by=costs:cost,saving")
    parser.add_argument("--sum-by-cau", action="store_true", help="Same as --group-by=savingCycles:type,cau")
    parser.add_argument("--costs-file", help="Path of input cost datas file. Must be used with --events-file")
    parser.add_argument("--events-file", help="Path of input cost datas file. Must be used with --costs-file")
    parser.add_argument("-o", "--output-file", help="Path of outputfile. 'datas = ' is appended on file beginning")

    args = parser.parse_args()    
    filters = {} if args.group_by != None or args.merge_by != None else False

    if args.group_by != None:
        if parse_filter_opt(args.group_by, 'group_by', filters) is False:
            sys.stderr.write("Please specify relevant fieldname with --group-by\n")
            parser.print_help() 
            return
    if args.merge_by != None:
        if parse_filter_opt(args.merge_by, 'merge_by', filters) is False:
            sys.stderr.write("Please specify relevant fieldname with --merge-by\n")
            parser.print_help() 
            return

    if (args.costs_file and not args.events_file) or (args.events_file and not args.costs_file):
        sys.stderr.write("--costs-file and --events-file options MUST be used together.\n")
        return 

    filters_preset = []
    if args.sum_by_cau:
        filters_preset.append('sum_by_cau')
    if args.sum_by_hour:
        filters_preset.append('sum_by_hour')
    return run({
        'costs_filepath': args.costs_file,
        'events_filepath': args.events_file,
        'no_raw_fields': args.no_raw_fields,
        'only_raw_fields': args.only_raw_fields,
        'output_file': args.output_file,
        'filters_preset': filters_preset
    }, filters)

if __name__ == "__main__":
    sys.exit(main())
