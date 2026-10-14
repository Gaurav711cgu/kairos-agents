/* global DOMException */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {saveCommand,savedCommands,clearCommand,LatestRead} from './investigation-client.ts';
const storage=()=>{const values=new Map();return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)}};
test('identities survive reloading client logic and remain workspace scoped',()=>{
 const store=storage(),body={task_id:'case',configuration:'loop-v4'};
 const first=saveCommand(store,'one','',body);
 assert.equal(saveCommand(store,'one','',body).key,first.key);
 assert.notEqual(saveCommand(store,'two','',body).key,first.key);
 assert.equal(savedCommands(store,'one').length,1);clearCommand(store,'one',first.key);assert.equal(savedCommands(store,'one').length,0);
});
test('storage failure prevents an unjournaled command',()=>{assert.throws(()=>saveCommand({getItem:()=>null,setItem:()=>{throw new DOMException('denied')}},'one','',{task_id:'case'}));});
test('late responses are rejected even if transport ignores abort',()=>{const reads=new LatestRead(),first=reads.begin(),second=reads.begin();assert.equal(first.signal.aborted,true);assert.equal(reads.current(first.version),false);assert.equal(reads.current(second.version),true);reads.stop();assert.equal(reads.current(second.version),false);});
