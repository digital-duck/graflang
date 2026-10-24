// Runtime for Cedar policies compiled by grafc. Standard library only.
//
// It implements Cedar's evaluation rules: values (bool, 64-bit long, string, entity, set, record), checked
// arithmetic, short-circuit && || and lazy `if`, `in` over an entity hierarchy, `has`, `like`, `is`, and the
// decision rule (any satisfied forbid denies; else any satisfied permit allows; else deny). A policy whose
// evaluation errors is skipped and reported in `Decision::errors`, exactly as the Cedar engine does; callers
// that want to fail closed use `Decision::allowed()`, which is false whenever any policy errored.
#![allow(dead_code)]

use std::collections::{BTreeMap, BTreeSet, HashMap};

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Uid {
    pub ty: String,
    pub id: String,
}

impl Uid {
    pub fn new(ty: &str, id: &str) -> Uid {
        Uid { ty: ty.to_string(), id: id.to_string() }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Value {
    Bool(bool),
    Long(i64),
    Str(String),
    Entity(Uid),
    Set(BTreeSet<Value>),
    Record(BTreeMap<String, Value>),
}

impl Value {
    fn type_name(&self) -> &'static str {
        match self {
            Value::Bool(_) => "bool",
            Value::Long(_) => "long",
            Value::Str(_) => "string",
            Value::Entity(_) => "entity",
            Value::Set(_) => "set",
            Value::Record(_) => "record",
        }
    }
}

#[derive(Clone, Debug)]
pub struct EvalError(pub String);
pub type Res<T> = Result<T, EvalError>;

fn err<T>(msg: String) -> Res<T> {
    Err(EvalError(msg))
}

#[derive(Clone, Debug, Default)]
pub struct EntityData {
    pub attrs: BTreeMap<String, Value>,
    pub parents: BTreeSet<Uid>,
}

#[derive(Clone, Debug)]
pub struct Request {
    pub principal: Uid,
    pub action: Uid,
    pub resource: Uid,
    pub context: BTreeMap<String, Value>,
    pub entities: HashMap<Uid, EntityData>,
}

impl Request {
    pub fn new(principal: Uid, action: Uid, resource: Uid) -> Request {
        Request { principal, action, resource, context: BTreeMap::new(), entities: HashMap::new() }
    }
}

// ---- the decision --------------------------------------------------------------------------------

#[derive(Clone, Debug, PartialEq)]
pub struct Decision {
    pub allow: bool,
    pub reasons: Vec<String>,
    pub errors: Vec<(String, String)>,
}

impl Decision {
    /// Fail closed: allowed only if Cedar says allow AND no policy errored.
    pub fn allowed(&self) -> bool {
        self.allow && self.errors.is_empty()
    }
}

pub struct DecisionBuilder {
    forbids: Vec<String>,
    permits: Vec<String>,
    errors: Vec<(String, String)>,
}

impl DecisionBuilder {
    pub fn new() -> DecisionBuilder {
        DecisionBuilder { forbids: vec![], permits: vec![], errors: vec![] }
    }

    pub fn run(&mut self, id: &str, is_forbid: bool, outcome: Res<bool>) {
        match outcome {
            Ok(true) => {
                if is_forbid { self.forbids.push(id.to_string()) } else { self.permits.push(id.to_string()) }
            }
            Ok(false) => {}
            Err(EvalError(m)) => self.errors.push((id.to_string(), m)),
        }
    }

    pub fn finish(self) -> Decision {
        if !self.forbids.is_empty() {
            Decision { allow: false, reasons: self.forbids, errors: self.errors }
        } else if !self.permits.is_empty() {
            Decision { allow: true, reasons: self.permits, errors: self.errors }
        } else {
            Decision { allow: false, reasons: vec![], errors: self.errors }
        }
    }
}

// ---- hierarchy -----------------------------------------------------------------------------------

/// `a in b`: a == b, or b is reachable from a through `parents` (reflexive, transitive).
pub fn entity_in(req: &Request, a: &Uid, b: &Uid) -> bool {
    if a == b {
        return true;
    }
    let mut seen: BTreeSet<Uid> = BTreeSet::new();
    let mut stack = vec![a.clone()];
    while let Some(cur) = stack.pop() {
        if let Some(data) = req.entities.get(&cur) {
            for p in &data.parents {
                if p == b {
                    return true;
                }
                if seen.insert(p.clone()) {
                    stack.push(p.clone());
                }
            }
        }
    }
    false
}

// ---- literals and variables ----------------------------------------------------------------------

pub fn lit_bool(b: bool) -> Res<Value> {
    Ok(Value::Bool(b))
}
pub fn lit_long(n: i64) -> Res<Value> {
    Ok(Value::Long(n))
}
pub fn lit_str(s: &str) -> Res<Value> {
    Ok(Value::Str(s.to_string()))
}
pub fn lit_entity(ty: &str, id: &str) -> Res<Value> {
    Ok(Value::Entity(Uid::new(ty, id)))
}
pub fn var_principal(req: &Request) -> Res<Value> {
    Ok(Value::Entity(req.principal.clone()))
}
pub fn var_action(req: &Request) -> Res<Value> {
    Ok(Value::Entity(req.action.clone()))
}
pub fn var_resource(req: &Request) -> Res<Value> {
    Ok(Value::Entity(req.resource.clone()))
}
pub fn var_context(req: &Request) -> Res<Value> {
    Ok(Value::Record(req.context.clone()))
}
pub fn set_lit(items: Vec<Res<Value>>) -> Res<Value> {
    let mut set = BTreeSet::new();
    for i in items {
        set.insert(i?);
    }
    Ok(Value::Set(set))
}
pub fn record_lit(items: Vec<(&str, Res<Value>)>) -> Res<Value> {
    let mut map = BTreeMap::new();
    for (k, v) in items {
        map.insert(k.to_string(), v?);
    }
    Ok(Value::Record(map))
}

// ---- operators -----------------------------------------------------------------------------------

pub fn as_bool(v: Res<Value>) -> Res<bool> {
    match v? {
        Value::Bool(b) => Ok(b),
        other => err(format!("expected bool, got {}", other.type_name())),
    }
}

pub fn and_(l: impl FnOnce() -> Res<Value>, r: impl FnOnce() -> Res<Value>) -> Res<Value> {
    if !as_bool(l())? {
        return Ok(Value::Bool(false));
    }
    Ok(Value::Bool(as_bool(r())?))
}

pub fn or_(l: impl FnOnce() -> Res<Value>, r: impl FnOnce() -> Res<Value>) -> Res<Value> {
    if as_bool(l())? {
        return Ok(Value::Bool(true));
    }
    Ok(Value::Bool(as_bool(r())?))
}

pub fn not_(v: Res<Value>) -> Res<Value> {
    Ok(Value::Bool(!as_bool(v)?))
}

pub fn if_(c: Res<Value>, t: impl FnOnce() -> Res<Value>, e: impl FnOnce() -> Res<Value>) -> Res<Value> {
    if as_bool(c)? { t() } else { e() }
}

pub fn eq(l: Res<Value>, r: Res<Value>) -> Res<Value> {
    let (l, r) = (l?, r?);
    Ok(Value::Bool(l == r))
}

pub fn neq(l: Res<Value>, r: Res<Value>) -> Res<Value> {
    let (l, r) = (l?, r?);
    Ok(Value::Bool(l != r))
}

fn long(v: Value, what: &str) -> Res<i64> {
    match v {
        Value::Long(n) => Ok(n),
        other => err(format!("{} expects long, got {}", what, other.type_name())),
    }
}

pub fn cmp(l: Res<Value>, r: Res<Value>, op: &str) -> Res<Value> {
    let (a, b) = (long(l?, op)?, long(r?, op)?);
    Ok(Value::Bool(match op {
        "<" => a < b,
        "<=" => a <= b,
        ">" => a > b,
        ">=" => a >= b,
        _ => return err(format!("unknown comparison {}", op)),
    }))
}

pub fn arith(l: Res<Value>, r: Res<Value>, op: char) -> Res<Value> {
    let (a, b) = (long(l?, "arithmetic")?, long(r?, "arithmetic")?);
    let out = match op {
        '+' => a.checked_add(b),
        '-' => a.checked_sub(b),
        '*' => a.checked_mul(b),
        _ => return err(format!("unknown operator {}", op)),
    };
    match out {
        Some(n) => Ok(Value::Long(n)),
        None => err("integer overflow".to_string()),
    }
}

pub fn neg(v: Res<Value>) -> Res<Value> {
    match long(v?, "negation")?.checked_neg() {
        Some(n) => Ok(Value::Long(n)),
        None => err("integer overflow".to_string()),
    }
}

pub fn in_(req: &Request, l: Res<Value>, r: Res<Value>) -> Res<Value> {
    let a = match l? {
        Value::Entity(u) => u,
        other => return err(format!("`in` expects an entity on the left, got {}", other.type_name())),
    };
    match r? {
        Value::Entity(b) => Ok(Value::Bool(entity_in(req, &a, &b))),
        Value::Set(items) => {
            for item in items {
                match item {
                    Value::Entity(b) => {
                        if entity_in(req, &a, &b) {
                            return Ok(Value::Bool(true));
                        }
                    }
                    other => return err(format!("`in` expects a set of entities, found {}", other.type_name())),
                }
            }
            Ok(Value::Bool(false))
        }
        other => err(format!("`in` expects an entity or set on the right, got {}", other.type_name())),
    }
}

pub fn is_(l: Res<Value>, ty: &str) -> Res<Value> {
    match l? {
        Value::Entity(u) => Ok(Value::Bool(u.ty == ty)),
        other => err(format!("`is` expects an entity, got {}", other.type_name())),
    }
}

pub fn attr(req: &Request, v: Res<Value>, name: &str) -> Res<Value> {
    match v? {
        Value::Record(map) => match map.get(name) {
            Some(x) => Ok(x.clone()),
            None => err(format!("record does not have the attribute {}", name)),
        },
        Value::Entity(u) => match req.entities.get(&u) {
            Some(data) => match data.attrs.get(name) {
                Some(x) => Ok(x.clone()),
                None => err(format!("{}::{} does not have the attribute {}", u.ty, u.id, name)),
            },
            None => err(format!("entity {}::{} does not exist", u.ty, u.id)),
        },
        other => err(format!("cannot read attribute {} of {}", name, other.type_name())),
    }
}

pub fn has(req: &Request, v: Res<Value>, name: &str) -> Res<Value> {
    match v? {
        Value::Record(map) => Ok(Value::Bool(map.contains_key(name))),
        Value::Entity(u) => Ok(Value::Bool(req.entities.get(&u).map_or(false, |d| d.attrs.contains_key(name)))),
        other => err(format!("`has` expects a record or entity, got {}", other.type_name())),
    }
}

/// `like`: `pattern` is a list of literal runs and wildcards (None) that match any number of characters.
pub fn like(v: Res<Value>, pattern: &[Option<&str>]) -> Res<Value> {
    let s = match v? {
        Value::Str(s) => s,
        other => return err(format!("`like` expects a string, got {}", other.type_name())),
    };
    let text: Vec<char> = s.chars().collect();
    // dp over positions: reachable[i] = pattern prefix can match text[..i]
    let mut reachable = vec![false; text.len() + 1];
    reachable[0] = true;
    for part in pattern {
        let mut next = vec![false; text.len() + 1];
        match part {
            None => {
                let mut any = false;
                for i in 0..=text.len() {
                    any = any || reachable[i];
                    next[i] = any;
                }
            }
            Some(lit) => {
                let lit: Vec<char> = lit.chars().collect();
                for i in 0..=text.len() {
                    if reachable[i] && i + lit.len() <= text.len() && text[i..i + lit.len()] == lit[..] {
                        next[i + lit.len()] = true;
                    }
                }
            }
        }
        reachable = next;
    }
    Ok(Value::Bool(reachable[text.len()]))
}

fn set_of(v: Value, what: &str) -> Res<BTreeSet<Value>> {
    match v {
        Value::Set(s) => Ok(s),
        other => err(format!("{} expects a set, got {}", what, other.type_name())),
    }
}

/// Set methods: contains, containsAll, containsAny, isEmpty.
pub fn method(recv: Res<Value>, name: &str, args: Vec<Res<Value>>) -> Res<Value> {
    let recv = recv?;
    let mut vals = Vec::new();
    for a in args {
        vals.push(a?);
    }
    let set = set_of(recv, name)?;
    match (name, vals.len()) {
        ("contains", 1) => Ok(Value::Bool(set.contains(&vals[0]))),
        ("isEmpty", 0) => Ok(Value::Bool(set.is_empty())),
        ("containsAll", 1) => {
            let other = set_of(vals.remove(0), name)?;
            Ok(Value::Bool(other.iter().all(|x| set.contains(x))))
        }
        ("containsAny", 1) => {
            let other = set_of(vals.remove(0), name)?;
            Ok(Value::Bool(other.iter().any(|x| set.contains(x))))
        }
        _ => err(format!("unsupported method {}/{}", name, vals.len())),
    }
}
