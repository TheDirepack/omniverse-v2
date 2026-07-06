(() => {
	const t = document.createElement("link").relList;
	if (t && t.supports && t.supports("modulepreload")) return;
	for (const l of document.querySelectorAll('link[rel="modulepreload"]')) r(l);
	new MutationObserver((l) => {
		for (const i of l)
			if (i.type === "childList")
				for (const o of i.addedNodes)
					o.tagName === "LINK" && o.rel === "modulepreload" && r(o);
	}).observe(document, { childList: !0, subtree: !0 });
	function n(l) {
		const i = {};
		return (
			l.integrity && (i.integrity = l.integrity),
			l.referrerPolicy && (i.referrerPolicy = l.referrerPolicy),
			l.crossOrigin === "use-credentials"
				? (i.credentials = "include")
				: l.crossOrigin === "anonymous"
					? (i.credentials = "omit")
					: (i.credentials = "same-origin"),
			i
		);
	}
	function r(l) {
		if (l.ep) return;
		l.ep = !0;
		const i = n(l);
		fetch(l.href, i);
	}
})();
function dc(e) {
	return e && e.__esModule && Object.hasOwn(e, "default") ? e.default : e;
}
var Zs = { exports: {} },
	ul = {},
	Js = { exports: {} },
	I = {}; /**
 * @license React
 * react.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var lr = Symbol.for("react.element"),
	fc = Symbol.for("react.portal"),
	pc = Symbol.for("react.fragment"),
	hc = Symbol.for("react.strict_mode"),
	mc = Symbol.for("react.profiler"),
	vc = Symbol.for("react.provider"),
	yc = Symbol.for("react.context"),
	gc = Symbol.for("react.forward_ref"),
	wc = Symbol.for("react.suspense"),
	Sc = Symbol.for("react.memo"),
	kc = Symbol.for("react.lazy"),
	Uo = Symbol.iterator;
function xc(e) {
	return e === null || typeof e != "object"
		? null
		: ((e = (Uo && e[Uo]) || e["@@iterator"]),
			typeof e == "function" ? e : null);
}
var qs = {
		isMounted: () => !1,
		enqueueForceUpdate: () => {},
		enqueueReplaceState: () => {},
		enqueueSetState: () => {},
	},
	bs = Object.assign,
	eu = {};
function mn(e, t, n) {
	(this.props = e),
		(this.context = t),
		(this.refs = eu),
		(this.updater = n || qs);
}
mn.prototype.isReactComponent = {};
mn.prototype.setState = function (e, t) {
	if (typeof e != "object" && typeof e != "function" && e != null)
		throw Error(
			"setState(...): takes an object of state variables to update or a function which returns an object of state variables.",
		);
	this.updater.enqueueSetState(this, e, t, "setState");
};
mn.prototype.forceUpdate = function (e) {
	this.updater.enqueueForceUpdate(this, e, "forceUpdate");
};
function tu() {}
tu.prototype = mn.prototype;
function Hi(e, t, n) {
	(this.props = e),
		(this.context = t),
		(this.refs = eu),
		(this.updater = n || qs);
}
var Ki = (Hi.prototype = new tu());
Ki.constructor = Hi;
bs(Ki, mn.prototype);
Ki.isPureReactComponent = !0;
var $o = Array.isArray,
	nu = Object.prototype.hasOwnProperty,
	Qi = { current: null },
	ru = { key: !0, ref: !0, __self: !0, __source: !0 };
function lu(e, t, n) {
	var r,
		l = {},
		i = null,
		o = null;
	if (t != null)
		for (r in (t.ref !== void 0 && (o = t.ref),
		t.key !== void 0 && (i = "" + t.key),
		t))
			nu.call(t, r) && !Object.hasOwn(ru, r) && (l[r] = t[r]);
	var s = arguments.length - 2;
	if (s === 1) l.children = n;
	else if (1 < s) {
		for (var u = Array(s), f = 0; f < s; f++) u[f] = arguments[f + 2];
		l.children = u;
	}
	if (e && e.defaultProps)
		for (r in ((s = e.defaultProps), s)) l[r] === void 0 && (l[r] = s[r]);
	return {
		$$typeof: lr,
		type: e,
		key: i,
		ref: o,
		props: l,
		_owner: Qi.current,
	};
}
function Nc(e, t) {
	return {
		$$typeof: lr,
		type: e.type,
		key: t,
		ref: e.ref,
		props: e.props,
		_owner: e._owner,
	};
}
function Yi(e) {
	return typeof e == "object" && e !== null && e.$$typeof === lr;
}
function Ec(e) {
	var t = { "=": "=0", ":": "=2" };
	return "$" + e.replace(/[=:]/g, (n) => t[n]);
}
var Wo = /\/+/g;
function El(e, t) {
	return typeof e == "object" && e !== null && e.key != null
		? Ec("" + e.key)
		: t.toString(36);
}
function _r(e, t, n, r, l) {
	var i = typeof e;
	(i === "undefined" || i === "boolean") && (e = null);
	var o = !1;
	if (e === null) o = !0;
	else
		switch (i) {
			case "string":
			case "number":
				o = !0;
				break;
			case "object":
				switch (e.$$typeof) {
					case lr:
					case fc:
						o = !0;
				}
		}
	if (o)
		return (
			(o = e),
			(l = l(o)),
			(e = r === "" ? "." + El(o, 0) : r),
			$o(l)
				? ((n = ""),
					e != null && (n = e.replace(Wo, "$&/") + "/"),
					_r(l, t, n, "", (f) => f))
				: l != null &&
					(Yi(l) &&
						(l = Nc(
							l,
							n +
								(!l.key || (o && o.key === l.key)
									? ""
									: ("" + l.key).replace(Wo, "$&/") + "/") +
								e,
						)),
					t.push(l)),
			1
		);
	if (((o = 0), (r = r === "" ? "." : r + ":"), $o(e)))
		for (var s = 0; s < e.length; s++) {
			i = e[s];
			var u = r + El(i, s);
			o += _r(i, t, n, u, l);
		}
	else if (((u = xc(e)), typeof u == "function"))
		for (e = u.call(e), s = 0; !(i = e.next()).done; )
			(i = i.value), (u = r + El(i, s++)), (o += _r(i, t, n, u, l));
	else if (i === "object")
		throw (
			((t = String(e)),
			Error(
				"Objects are not valid as a React child (found: " +
					(t === "[object Object]"
						? "object with keys {" + Object.keys(e).join(", ") + "}"
						: t) +
					"). If you meant to render a collection of children, use an array instead.",
			))
		);
	return o;
}
function ar(e, t, n) {
	if (e == null) return e;
	var r = [],
		l = 0;
	return _r(e, r, "", "", (i) => t.call(n, i, l++)), r;
}
function Cc(e) {
	if (e._status === -1) {
		var t = e._result;
		(t = t()),
			t.then(
				(n) => {
					(e._status === 0 || e._status === -1) &&
						((e._status = 1), (e._result = n));
				},
				(n) => {
					(e._status === 0 || e._status === -1) &&
						((e._status = 2), (e._result = n));
				},
			),
			e._status === -1 && ((e._status = 0), (e._result = t));
	}
	if (e._status === 1) return e._result.default;
	throw e._result;
}
var me = { current: null },
	jr = { transition: null },
	_c = {
		ReactCurrentDispatcher: me,
		ReactCurrentBatchConfig: jr,
		ReactCurrentOwner: Qi,
	};
function iu() {
	throw Error("act(...) is not supported in production builds of React.");
}
I.Children = {
	map: ar,
	forEach: (e, t, n) => {
		ar(
			e,
			function () {
				t.apply(this, arguments);
			},
			n,
		);
	},
	count: (e) => {
		var t = 0;
		return (
			ar(e, () => {
				t++;
			}),
			t
		);
	},
	toArray: (e) => ar(e, (t) => t) || [],
	only: (e) => {
		if (!Yi(e))
			throw Error(
				"React.Children.only expected to receive a single React element child.",
			);
		return e;
	},
};
I.Component = mn;
I.Fragment = pc;
I.Profiler = mc;
I.PureComponent = Hi;
I.StrictMode = hc;
I.Suspense = wc;
I.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = _c;
I.act = iu;
I.cloneElement = function (e, t, n) {
	if (e == null)
		throw Error(
			"React.cloneElement(...): The argument must be a React element, but you passed " +
				e +
				".",
		);
	var r = bs({}, e.props),
		l = e.key,
		i = e.ref,
		o = e._owner;
	if (t != null) {
		if (
			(t.ref !== void 0 && ((i = t.ref), (o = Qi.current)),
			t.key !== void 0 && (l = "" + t.key),
			e.type && e.type.defaultProps)
		)
			var s = e.type.defaultProps;
		for (u in t)
			nu.call(t, u) &&
				!Object.hasOwn(ru, u) &&
				(r[u] = t[u] === void 0 && s !== void 0 ? s[u] : t[u]);
	}
	var u = arguments.length - 2;
	if (u === 1) r.children = n;
	else if (1 < u) {
		s = Array(u);
		for (var f = 0; f < u; f++) s[f] = arguments[f + 2];
		r.children = s;
	}
	return { $$typeof: lr, type: e.type, key: l, ref: i, props: r, _owner: o };
};
I.createContext = (e) => (
	(e = {
		$$typeof: yc,
		_currentValue: e,
		_currentValue2: e,
		_threadCount: 0,
		Provider: null,
		Consumer: null,
		_defaultValue: null,
		_globalName: null,
	}),
	(e.Provider = { $$typeof: vc, _context: e }),
	(e.Consumer = e)
);
I.createElement = lu;
I.createFactory = (e) => {
	var t = lu.bind(null, e);
	return (t.type = e), t;
};
I.createRef = () => ({ current: null });
I.forwardRef = (e) => ({ $$typeof: gc, render: e });
I.isValidElement = Yi;
I.lazy = (e) => ({
	$$typeof: kc,
	_payload: { _status: -1, _result: e },
	_init: Cc,
});
I.memo = (e, t) => ({
	$$typeof: Sc,
	type: e,
	compare: t === void 0 ? null : t,
});
I.startTransition = (e) => {
	var t = jr.transition;
	jr.transition = {};
	try {
		e();
	} finally {
		jr.transition = t;
	}
};
I.unstable_act = iu;
I.useCallback = (e, t) => me.current.useCallback(e, t);
I.useContext = (e) => me.current.useContext(e);
I.useDebugValue = () => {};
I.useDeferredValue = (e) => me.current.useDeferredValue(e);
I.useEffect = (e, t) => me.current.useEffect(e, t);
I.useId = () => me.current.useId();
I.useImperativeHandle = (e, t, n) => me.current.useImperativeHandle(e, t, n);
I.useInsertionEffect = (e, t) => me.current.useInsertionEffect(e, t);
I.useLayoutEffect = (e, t) => me.current.useLayoutEffect(e, t);
I.useMemo = (e, t) => me.current.useMemo(e, t);
I.useReducer = (e, t, n) => me.current.useReducer(e, t, n);
I.useRef = (e) => me.current.useRef(e);
I.useState = (e) => me.current.useState(e);
I.useSyncExternalStore = (e, t, n) => me.current.useSyncExternalStore(e, t, n);
I.useTransition = () => me.current.useTransition();
I.version = "18.3.1";
Js.exports = I;
var R = Js.exports;
const jc = dc(R); /**
 * @license React
 * react-jsx-runtime.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var Pc = R,
	Tc = Symbol.for("react.element"),
	Lc = Symbol.for("react.fragment"),
	zc = Object.prototype.hasOwnProperty,
	Rc = Pc.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner,
	Oc = { key: !0, ref: !0, __self: !0, __source: !0 };
function ou(e, t, n) {
	var r,
		l = {},
		i = null,
		o = null;
	n !== void 0 && (i = "" + n),
		t.key !== void 0 && (i = "" + t.key),
		t.ref !== void 0 && (o = t.ref);
	for (r in t) zc.call(t, r) && !Object.hasOwn(Oc, r) && (l[r] = t[r]);
	if (e && e.defaultProps)
		for (r in ((t = e.defaultProps), t)) l[r] === void 0 && (l[r] = t[r]);
	return {
		$$typeof: Tc,
		type: e,
		key: i,
		ref: o,
		props: l,
		_owner: Rc.current,
	};
}
ul.Fragment = Lc;
ul.jsx = ou;
ul.jsxs = ou;
Zs.exports = ul;
var c = Zs.exports,
	Jl = {},
	su = { exports: {} },
	_e = {},
	uu = { exports: {} },
	au = {}; /**
 * @license React
 * scheduler.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
((e) => {
	function t(_, S) {
		var O = _.length;
		_.push(S);
		for (; 0 < O; ) {
			var $ = (O - 1) >>> 1,
				G = _[$];
			if (0 < l(G, S)) (_[$] = S), (_[O] = G), (O = $);
			else break;
		}
	}
	function n(_) {
		return _.length === 0 ? null : _[0];
	}
	function r(_) {
		if (_.length === 0) return null;
		var S = _[0],
			O = _.pop();
		if (O !== S) {
			_[0] = O;
			for (var $ = 0, G = _.length, Wt = G >>> 1; $ < Wt; ) {
				var We = 2 * ($ + 1) - 1,
					z = _[We],
					F = We + 1,
					Z = _[F];
				if (0 > l(z, O))
					F < G && 0 > l(Z, z)
						? ((_[$] = Z), (_[F] = O), ($ = F))
						: ((_[$] = z), (_[We] = O), ($ = We));
				else if (F < G && 0 > l(Z, O)) (_[$] = Z), (_[F] = O), ($ = F);
				else break;
			}
		}
		return S;
	}
	function l(_, S) {
		var O = _.sortIndex - S.sortIndex;
		return O !== 0 ? O : _.id - S.id;
	}
	if (typeof performance == "object" && typeof performance.now == "function") {
		var i = performance;
		e.unstable_now = () => i.now();
	} else {
		var o = Date,
			s = o.now();
		e.unstable_now = () => o.now() - s;
	}
	var u = [],
		f = [],
		v = 1,
		h = null,
		m = 3,
		g = !1,
		x = !1,
		E = !1,
		D = typeof setTimeout == "function" ? setTimeout : null,
		p = typeof clearTimeout == "function" ? clearTimeout : null,
		a = typeof setImmediate < "u" ? setImmediate : null;
	typeof navigator < "u" &&
		navigator.scheduling !== void 0 &&
		navigator.scheduling.isInputPending !== void 0 &&
		navigator.scheduling.isInputPending.bind(navigator.scheduling);
	function d(_) {
		for (var S = n(f); S !== null; ) {
			if (S.callback === null) r(f);
			else if (S.startTime <= _)
				r(f), (S.sortIndex = S.expirationTime), t(u, S);
			else break;
			S = n(f);
		}
	}
	function y(_) {
		if (((E = !1), d(_), !x))
			if (n(u) !== null) (x = !0), Et(N);
			else {
				var S = n(f);
				S !== null && Ct(y, S.startTime - _);
			}
	}
	function N(_, S) {
		(x = !1), E && ((E = !1), p(L), (L = -1)), (g = !0);
		var O = m;
		try {
			for (
				d(S), h = n(u);
				h !== null && (!(h.expirationTime > S) || (_ && !U()));
			) {
				var $ = h.callback;
				if (typeof $ == "function") {
					(h.callback = null), (m = h.priorityLevel);
					var G = $(h.expirationTime <= S);
					(S = e.unstable_now()),
						typeof G == "function" ? (h.callback = G) : h === n(u) && r(u),
						d(S);
				} else r(u);
				h = n(u);
			}
			if (h !== null) var Wt = !0;
			else {
				var We = n(f);
				We !== null && Ct(y, We.startTime - S), (Wt = !1);
			}
			return Wt;
		} finally {
			(h = null), (m = O), (g = !1);
		}
	}
	var k = !1,
		C = null,
		L = -1,
		j = 5,
		P = -1;
	function U() {
		return !(e.unstable_now() - P < j);
	}
	function fe() {
		if (C !== null) {
			var _ = e.unstable_now();
			P = _;
			var S = !0;
			try {
				S = C(!0, _);
			} finally {
				S ? Ye() : ((k = !1), (C = null));
			}
		} else k = !1;
	}
	var Ye;
	if (typeof a == "function")
		Ye = () => {
			a(fe);
		};
	else if (typeof MessageChannel < "u") {
		var $t = new MessageChannel(),
			wn = $t.port2;
		($t.port1.onmessage = fe),
			(Ye = () => {
				wn.postMessage(null);
			});
	} else
		Ye = () => {
			D(fe, 0);
		};
	function Et(_) {
		(C = _), k || ((k = !0), Ye());
	}
	function Ct(_, S) {
		L = D(() => {
			_(e.unstable_now());
		}, S);
	}
	(e.unstable_IdlePriority = 5),
		(e.unstable_ImmediatePriority = 1),
		(e.unstable_LowPriority = 4),
		(e.unstable_NormalPriority = 3),
		(e.unstable_Profiling = null),
		(e.unstable_UserBlockingPriority = 2),
		(e.unstable_cancelCallback = (_) => {
			_.callback = null;
		}),
		(e.unstable_continueExecution = () => {
			x || g || ((x = !0), Et(N));
		}),
		(e.unstable_forceFrameRate = (_) => {
			0 > _ || 125 < _
				? console.error(
						"forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported",
					)
				: (j = 0 < _ ? Math.floor(1e3 / _) : 5);
		}),
		(e.unstable_getCurrentPriorityLevel = () => m),
		(e.unstable_getFirstCallbackNode = () => n(u)),
		(e.unstable_next = (_) => {
			switch (m) {
				case 1:
				case 2:
				case 3: {
					var S = 3;
					break;
				}
				default:
					S = m;
			}
			var O = m;
			m = S;
			try {
				return _();
			} finally {
				m = O;
			}
		}),
		(e.unstable_pauseExecution = () => {}),
		(e.unstable_requestPaint = () => {}),
		(e.unstable_runWithPriority = (_, S) => {
			switch (_) {
				case 1:
				case 2:
				case 3:
				case 4:
				case 5:
					break;
				default:
					_ = 3;
			}
			var O = m;
			m = _;
			try {
				return S();
			} finally {
				m = O;
			}
		}),
		(e.unstable_scheduleCallback = (_, S, O) => {
			var $ = e.unstable_now();
			switch (
				(typeof O == "object" && O !== null
					? ((O = O.delay), (O = typeof O == "number" && 0 < O ? $ + O : $))
					: (O = $),
				_)
			) {
				case 1: {
					var G = -1;
					break;
				}
				case 2:
					G = 250;
					break;
				case 5:
					G = 1073741823;
					break;
				case 4:
					G = 1e4;
					break;
				default:
					G = 5e3;
			}
			return (
				(G = O + G),
				(_ = {
					id: v++,
					callback: S,
					priorityLevel: _,
					startTime: O,
					expirationTime: G,
					sortIndex: -1,
				}),
				O > $
					? ((_.sortIndex = O),
						t(f, _),
						n(u) === null &&
							_ === n(f) &&
							(E ? (p(L), (L = -1)) : (E = !0), Ct(y, O - $)))
					: ((_.sortIndex = G), t(u, _), x || g || ((x = !0), Et(N))),
				_
			);
		}),
		(e.unstable_shouldYield = U),
		(e.unstable_wrapCallback = (_) => {
			var S = m;
			return function () {
				var O = m;
				m = S;
				try {
					return _.apply(this, arguments);
				} finally {
					m = O;
				}
			};
		});
})(au);
uu.exports = au;
var Dc = uu.exports; /**
 * @license React
 * react-dom.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var Ic = R,
	Ce = Dc;
function w(e) {
	for (
		var t = "https://reactjs.org/docs/error-decoder.html?invariant=" + e, n = 1;
		n < arguments.length;
		n++
	)
		t += "&args[]=" + encodeURIComponent(arguments[n]);
	return (
		"Minified React error #" +
		e +
		"; visit " +
		t +
		" for the full message or use the non-minified dev environment for full errors and additional helpful warnings."
	);
}
var cu = new Set(),
	Wn = {};
function At(e, t) {
	un(e, t), un(e + "Capture", t);
}
function un(e, t) {
	for (Wn[e] = t, e = 0; e < t.length; e++) cu.add(t[e]);
}
var be = !(
		typeof window > "u" ||
		typeof window.document > "u" ||
		typeof window.document.createElement > "u"
	),
	ql = Object.prototype.hasOwnProperty,
	Fc =
		/^[:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD][:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\-.0-9\u00B7\u0300-\u036F\u203F-\u2040]*$/,
	Bo = {},
	Vo = {};
function Mc(e) {
	return ql.call(Vo, e)
		? !0
		: ql.call(Bo, e)
			? !1
			: Fc.test(e)
				? (Vo[e] = !0)
				: ((Bo[e] = !0), !1);
}
function Ac(e, t, n, r) {
	if (n !== null && n.type === 0) return !1;
	switch (typeof t) {
		case "function":
		case "symbol":
			return !0;
		case "boolean":
			return r
				? !1
				: n !== null
					? !n.acceptsBooleans
					: ((e = e.toLowerCase().slice(0, 5)), e !== "data-" && e !== "aria-");
		default:
			return !1;
	}
}
function Uc(e, t, n, r) {
	if (t === null || typeof t > "u" || Ac(e, t, n, r)) return !0;
	if (r) return !1;
	if (n !== null)
		switch (n.type) {
			case 3:
				return !t;
			case 4:
				return t === !1;
			case 5:
				return isNaN(t);
			case 6:
				return isNaN(t) || 1 > t;
		}
	return !1;
}
function ve(e, t, n, r, l, i, o) {
	(this.acceptsBooleans = t === 2 || t === 3 || t === 4),
		(this.attributeName = r),
		(this.attributeNamespace = l),
		(this.mustUseProperty = n),
		(this.propertyName = e),
		(this.type = t),
		(this.sanitizeURL = i),
		(this.removeEmptyString = o);
}
var se = {};
"children dangerouslySetInnerHTML defaultValue defaultChecked innerHTML suppressContentEditableWarning suppressHydrationWarning style"
	.split(" ")
	.forEach((e) => {
		se[e] = new ve(e, 0, !1, e, null, !1, !1);
	});
[
	["acceptCharset", "accept-charset"],
	["className", "class"],
	["htmlFor", "for"],
	["httpEquiv", "http-equiv"],
].forEach((e) => {
	var t = e[0];
	se[t] = new ve(t, 1, !1, e[1], null, !1, !1);
});
["contentEditable", "draggable", "spellCheck", "value"].forEach((e) => {
	se[e] = new ve(e, 2, !1, e.toLowerCase(), null, !1, !1);
});
[
	"autoReverse",
	"externalResourcesRequired",
	"focusable",
	"preserveAlpha",
].forEach((e) => {
	se[e] = new ve(e, 2, !1, e, null, !1, !1);
});
"allowFullScreen async autoFocus autoPlay controls default defer disabled disablePictureInPicture disableRemotePlayback formNoValidate hidden loop noModule noValidate open playsInline readOnly required reversed scoped seamless itemScope"
	.split(" ")
	.forEach((e) => {
		se[e] = new ve(e, 3, !1, e.toLowerCase(), null, !1, !1);
	});
["checked", "multiple", "muted", "selected"].forEach((e) => {
	se[e] = new ve(e, 3, !0, e, null, !1, !1);
});
["capture", "download"].forEach((e) => {
	se[e] = new ve(e, 4, !1, e, null, !1, !1);
});
["cols", "rows", "size", "span"].forEach((e) => {
	se[e] = new ve(e, 6, !1, e, null, !1, !1);
});
["rowSpan", "start"].forEach((e) => {
	se[e] = new ve(e, 5, !1, e.toLowerCase(), null, !1, !1);
});
var Gi = /[-:]([a-z])/g;
function Xi(e) {
	return e[1].toUpperCase();
}
"accent-height alignment-baseline arabic-form baseline-shift cap-height clip-path clip-rule color-interpolation color-interpolation-filters color-profile color-rendering dominant-baseline enable-background fill-opacity fill-rule flood-color flood-opacity font-family font-size font-size-adjust font-stretch font-style font-variant font-weight glyph-name glyph-orientation-horizontal glyph-orientation-vertical horiz-adv-x horiz-origin-x image-rendering letter-spacing lighting-color marker-end marker-mid marker-start overline-position overline-thickness paint-order panose-1 pointer-events rendering-intent shape-rendering stop-color stop-opacity strikethrough-position strikethrough-thickness stroke-dasharray stroke-dashoffset stroke-linecap stroke-linejoin stroke-miterlimit stroke-opacity stroke-width text-anchor text-decoration text-rendering underline-position underline-thickness unicode-bidi unicode-range units-per-em v-alphabetic v-hanging v-ideographic v-mathematical vector-effect vert-adv-y vert-origin-x vert-origin-y word-spacing writing-mode xmlns:xlink x-height"
	.split(" ")
	.forEach((e) => {
		var t = e.replace(Gi, Xi);
		se[t] = new ve(t, 1, !1, e, null, !1, !1);
	});
"xlink:actuate xlink:arcrole xlink:role xlink:show xlink:title xlink:type"
	.split(" ")
	.forEach((e) => {
		var t = e.replace(Gi, Xi);
		se[t] = new ve(t, 1, !1, e, "http://www.w3.org/1999/xlink", !1, !1);
	});
["xml:base", "xml:lang", "xml:space"].forEach((e) => {
	var t = e.replace(Gi, Xi);
	se[t] = new ve(t, 1, !1, e, "http://www.w3.org/XML/1998/namespace", !1, !1);
});
["tabIndex", "crossOrigin"].forEach((e) => {
	se[e] = new ve(e, 1, !1, e.toLowerCase(), null, !1, !1);
});
se.xlinkHref = new ve(
	"xlinkHref",
	1,
	!1,
	"xlink:href",
	"http://www.w3.org/1999/xlink",
	!0,
	!1,
);
["src", "href", "action", "formAction"].forEach((e) => {
	se[e] = new ve(e, 1, !1, e.toLowerCase(), null, !0, !0);
});
function Zi(e, t, n, r) {
	var l = Object.hasOwn(se, t) ? se[t] : null;
	(l !== null
		? l.type !== 0
		: r ||
			!(2 < t.length) ||
			(t[0] !== "o" && t[0] !== "O") ||
			(t[1] !== "n" && t[1] !== "N")) &&
		(Uc(t, n, l, r) && (n = null),
		r || l === null
			? Mc(t) && (n === null ? e.removeAttribute(t) : e.setAttribute(t, "" + n))
			: l.mustUseProperty
				? (e[l.propertyName] = n === null ? (l.type === 3 ? !1 : "") : n)
				: ((t = l.attributeName),
					(r = l.attributeNamespace),
					n === null
						? e.removeAttribute(t)
						: ((l = l.type),
							(n = l === 3 || (l === 4 && n === !0) ? "" : "" + n),
							r ? e.setAttributeNS(r, t, n) : e.setAttribute(t, n))));
}
var rt = Ic.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED,
	cr = Symbol.for("react.element"),
	Vt = Symbol.for("react.portal"),
	Ht = Symbol.for("react.fragment"),
	Ji = Symbol.for("react.strict_mode"),
	bl = Symbol.for("react.profiler"),
	du = Symbol.for("react.provider"),
	fu = Symbol.for("react.context"),
	qi = Symbol.for("react.forward_ref"),
	ei = Symbol.for("react.suspense"),
	ti = Symbol.for("react.suspense_list"),
	bi = Symbol.for("react.memo"),
	it = Symbol.for("react.lazy"),
	pu = Symbol.for("react.offscreen"),
	Ho = Symbol.iterator;
function Sn(e) {
	return e === null || typeof e != "object"
		? null
		: ((e = (Ho && e[Ho]) || e["@@iterator"]),
			typeof e == "function" ? e : null);
}
var Y = Object.assign,
	Cl;
function Pn(e) {
	if (Cl === void 0)
		try {
			throw Error();
		} catch (n) {
			var t = n.stack.trim().match(/\n( *(at )?)/);
			Cl = (t && t[1]) || "";
		}
	return (
		`
` +
		Cl +
		e
	);
}
var _l = !1;
function jl(e, t) {
	if (!e || _l) return "";
	_l = !0;
	var n = Error.prepareStackTrace;
	Error.prepareStackTrace = void 0;
	try {
		if (t)
			if (
				((t = () => {
					throw Error();
				}),
				Object.defineProperty(t.prototype, "props", {
					set: () => {
						throw Error();
					},
				}),
				typeof Reflect == "object" && Reflect.construct)
			) {
				try {
					Reflect.construct(t, []);
				} catch (f) {
					var r = f;
				}
				Reflect.construct(e, [], t);
			} else {
				try {
					t.call();
				} catch (f) {
					r = f;
				}
				e.call(t.prototype);
			}
		else {
			try {
				throw Error();
			} catch (f) {
				r = f;
			}
			e();
		}
	} catch (f) {
		if (f && r && typeof f.stack == "string") {
			for (
				var l = f.stack.split(`
`),
					i = r.stack.split(`
`),
					o = l.length - 1,
					s = i.length - 1;
				1 <= o && 0 <= s && l[o] !== i[s];
			)
				s--;
			for (; 1 <= o && 0 <= s; o--, s--)
				if (l[o] !== i[s]) {
					if (o !== 1 || s !== 1)
						do
							if ((o--, s--, 0 > s || l[o] !== i[s])) {
								var u =
									`
` + l[o].replace(" at new ", " at ");
								return (
									e.displayName &&
										u.includes("<anonymous>") &&
										(u = u.replace("<anonymous>", e.displayName)),
									u
								);
							}
						while (1 <= o && 0 <= s);
					break;
				}
		}
	} finally {
		(_l = !1), (Error.prepareStackTrace = n);
	}
	return (e = e ? e.displayName || e.name : "") ? Pn(e) : "";
}
function $c(e) {
	switch (e.tag) {
		case 5:
			return Pn(e.type);
		case 16:
			return Pn("Lazy");
		case 13:
			return Pn("Suspense");
		case 19:
			return Pn("SuspenseList");
		case 0:
		case 2:
		case 15:
			return (e = jl(e.type, !1)), e;
		case 11:
			return (e = jl(e.type.render, !1)), e;
		case 1:
			return (e = jl(e.type, !0)), e;
		default:
			return "";
	}
}
function ni(e) {
	if (e == null) return null;
	if (typeof e == "function") return e.displayName || e.name || null;
	if (typeof e == "string") return e;
	switch (e) {
		case Ht:
			return "Fragment";
		case Vt:
			return "Portal";
		case bl:
			return "Profiler";
		case Ji:
			return "StrictMode";
		case ei:
			return "Suspense";
		case ti:
			return "SuspenseList";
	}
	if (typeof e == "object")
		switch (e.$$typeof) {
			case fu:
				return (e.displayName || "Context") + ".Consumer";
			case du:
				return (e._context.displayName || "Context") + ".Provider";
			case qi: {
				var t = e.render;
				return (
					(e = e.displayName),
					e ||
						((e = t.displayName || t.name || ""),
						(e = e !== "" ? "ForwardRef(" + e + ")" : "ForwardRef")),
					e
				);
			}
			case bi:
				return (
					(t = e.displayName || null), t !== null ? t : ni(e.type) || "Memo"
				);
			case it:
				(t = e._payload), (e = e._init);
				try {
					return ni(e(t));
				} catch {}
		}
	return null;
}
function Wc(e) {
	var t = e.type;
	switch (e.tag) {
		case 24:
			return "Cache";
		case 9:
			return (t.displayName || "Context") + ".Consumer";
		case 10:
			return (t._context.displayName || "Context") + ".Provider";
		case 18:
			return "DehydratedFragment";
		case 11:
			return (
				(e = t.render),
				(e = e.displayName || e.name || ""),
				t.displayName || (e !== "" ? "ForwardRef(" + e + ")" : "ForwardRef")
			);
		case 7:
			return "Fragment";
		case 5:
			return t;
		case 4:
			return "Portal";
		case 3:
			return "Root";
		case 6:
			return "Text";
		case 16:
			return ni(t);
		case 8:
			return t === Ji ? "StrictMode" : "Mode";
		case 22:
			return "Offscreen";
		case 12:
			return "Profiler";
		case 21:
			return "Scope";
		case 13:
			return "Suspense";
		case 19:
			return "SuspenseList";
		case 25:
			return "TracingMarker";
		case 1:
		case 0:
		case 17:
		case 2:
		case 14:
		case 15:
			if (typeof t == "function") return t.displayName || t.name || null;
			if (typeof t == "string") return t;
	}
	return null;
}
function wt(e) {
	switch (typeof e) {
		case "boolean":
		case "number":
		case "string":
		case "undefined":
			return e;
		case "object":
			return e;
		default:
			return "";
	}
}
function hu(e) {
	var t = e.type;
	return (
		(e = e.nodeName) &&
		e.toLowerCase() === "input" &&
		(t === "checkbox" || t === "radio")
	);
}
function Bc(e) {
	var t = hu(e) ? "checked" : "value",
		n = Object.getOwnPropertyDescriptor(e.constructor.prototype, t),
		r = "" + e[t];
	if (
		!Object.hasOwn(e, t) &&
		typeof n < "u" &&
		typeof n.get == "function" &&
		typeof n.set == "function"
	) {
		var l = n.get,
			i = n.set;
		return (
			Object.defineProperty(e, t, {
				configurable: !0,
				get: function () {
					return l.call(this);
				},
				set: function (o) {
					(r = "" + o), i.call(this, o);
				},
			}),
			Object.defineProperty(e, t, { enumerable: n.enumerable }),
			{
				getValue: () => r,
				setValue: (o) => {
					r = "" + o;
				},
				stopTracking: () => {
					(e._valueTracker = null), delete e[t];
				},
			}
		);
	}
}
function dr(e) {
	e._valueTracker || (e._valueTracker = Bc(e));
}
function mu(e) {
	if (!e) return !1;
	var t = e._valueTracker;
	if (!t) return !0;
	var n = t.getValue(),
		r = "";
	return (
		e && (r = hu(e) ? (e.checked ? "true" : "false") : e.value),
		(e = r),
		e !== n ? (t.setValue(e), !0) : !1
	);
}
function Ar(e) {
	if (((e = e || (typeof document < "u" ? document : void 0)), typeof e > "u"))
		return null;
	try {
		return e.activeElement || e.body;
	} catch {
		return e.body;
	}
}
function ri(e, t) {
	var n = t.checked;
	return Y({}, t, {
		defaultChecked: void 0,
		defaultValue: void 0,
		value: void 0,
		checked: n ?? e._wrapperState.initialChecked,
	});
}
function Ko(e, t) {
	var n = t.defaultValue == null ? "" : t.defaultValue,
		r = t.checked != null ? t.checked : t.defaultChecked;
	(n = wt(t.value != null ? t.value : n)),
		(e._wrapperState = {
			initialChecked: r,
			initialValue: n,
			controlled:
				t.type === "checkbox" || t.type === "radio"
					? t.checked != null
					: t.value != null,
		});
}
function vu(e, t) {
	(t = t.checked), t != null && Zi(e, "checked", t, !1);
}
function li(e, t) {
	vu(e, t);
	var n = wt(t.value),
		r = t.type;
	if (n != null)
		r === "number"
			? ((n === 0 && e.value === "") || e.value != n) && (e.value = "" + n)
			: e.value !== "" + n && (e.value = "" + n);
	else if (r === "submit" || r === "reset") {
		e.removeAttribute("value");
		return;
	}
	Object.hasOwn(t, "value")
		? ii(e, t.type, n)
		: Object.hasOwn(t, "defaultValue") && ii(e, t.type, wt(t.defaultValue)),
		t.checked == null &&
			t.defaultChecked != null &&
			(e.defaultChecked = !!t.defaultChecked);
}
function Qo(e, t, n) {
	if (Object.hasOwn(t, "value") || Object.hasOwn(t, "defaultValue")) {
		var r = t.type;
		if (
			!(
				(r !== "submit" && r !== "reset") ||
				(t.value !== void 0 && t.value !== null)
			)
		)
			return;
		(t = "" + e._wrapperState.initialValue),
			n || t === e.value || (e.value = t),
			(e.defaultValue = t);
	}
	(n = e.name),
		n !== "" && (e.name = ""),
		(e.defaultChecked = !!e._wrapperState.initialChecked),
		n !== "" && (e.name = n);
}
function ii(e, t, n) {
	(t !== "number" || Ar(e.ownerDocument) !== e) &&
		(n == null
			? (e.defaultValue = "" + e._wrapperState.initialValue)
			: e.defaultValue !== "" + n && (e.defaultValue = "" + n));
}
var Tn = Array.isArray;
function tn(e, t, n, r) {
	if (((e = e.options), t)) {
		t = {};
		for (var l = 0; l < n.length; l++) t["$" + n[l]] = !0;
		for (n = 0; n < e.length; n++)
			(l = Object.hasOwn(t, "$" + e[n].value)),
				e[n].selected !== l && (e[n].selected = l),
				l && r && (e[n].defaultSelected = !0);
	} else {
		for (n = "" + wt(n), t = null, l = 0; l < e.length; l++) {
			if (e[l].value === n) {
				(e[l].selected = !0), r && (e[l].defaultSelected = !0);
				return;
			}
			t !== null || e[l].disabled || (t = e[l]);
		}
		t !== null && (t.selected = !0);
	}
}
function oi(e, t) {
	if (t.dangerouslySetInnerHTML != null) throw Error(w(91));
	return Y({}, t, {
		value: void 0,
		defaultValue: void 0,
		children: "" + e._wrapperState.initialValue,
	});
}
function Yo(e, t) {
	var n = t.value;
	if (n == null) {
		if (((n = t.children), (t = t.defaultValue), n != null)) {
			if (t != null) throw Error(w(92));
			if (Tn(n)) {
				if (1 < n.length) throw Error(w(93));
				n = n[0];
			}
			t = n;
		}
		t == null && (t = ""), (n = t);
	}
	e._wrapperState = { initialValue: wt(n) };
}
function yu(e, t) {
	var n = wt(t.value),
		r = wt(t.defaultValue);
	n != null &&
		((n = "" + n),
		n !== e.value && (e.value = n),
		t.defaultValue == null && e.defaultValue !== n && (e.defaultValue = n)),
		r != null && (e.defaultValue = "" + r);
}
function Go(e) {
	var t = e.textContent;
	t === e._wrapperState.initialValue && t !== "" && t !== null && (e.value = t);
}
function gu(e) {
	switch (e) {
		case "svg":
			return "http://www.w3.org/2000/svg";
		case "math":
			return "http://www.w3.org/1998/Math/MathML";
		default:
			return "http://www.w3.org/1999/xhtml";
	}
}
function si(e, t) {
	return e == null || e === "http://www.w3.org/1999/xhtml"
		? gu(t)
		: e === "http://www.w3.org/2000/svg" && t === "foreignObject"
			? "http://www.w3.org/1999/xhtml"
			: e;
}
var fr,
	wu = ((e) =>
		typeof MSApp < "u" && MSApp.execUnsafeLocalFunction
			? (t, n, r, l) => {
					MSApp.execUnsafeLocalFunction(() => e(t, n, r, l));
				}
			: e)((e, t) => {
		if (e.namespaceURI !== "http://www.w3.org/2000/svg" || "innerHTML" in e)
			e.innerHTML = t;
		else {
			for (
				fr = fr || document.createElement("div"),
					fr.innerHTML = "<svg>" + t.valueOf().toString() + "</svg>",
					t = fr.firstChild;
				e.firstChild;
			)
				e.removeChild(e.firstChild);
			for (; t.firstChild; ) e.appendChild(t.firstChild);
		}
	});
function Bn(e, t) {
	if (t) {
		var n = e.firstChild;
		if (n && n === e.lastChild && n.nodeType === 3) {
			n.nodeValue = t;
			return;
		}
	}
	e.textContent = t;
}
var Rn = {
		animationIterationCount: !0,
		aspectRatio: !0,
		borderImageOutset: !0,
		borderImageSlice: !0,
		borderImageWidth: !0,
		boxFlex: !0,
		boxFlexGroup: !0,
		boxOrdinalGroup: !0,
		columnCount: !0,
		columns: !0,
		flex: !0,
		flexGrow: !0,
		flexPositive: !0,
		flexShrink: !0,
		flexNegative: !0,
		flexOrder: !0,
		gridArea: !0,
		gridRow: !0,
		gridRowEnd: !0,
		gridRowSpan: !0,
		gridRowStart: !0,
		gridColumn: !0,
		gridColumnEnd: !0,
		gridColumnSpan: !0,
		gridColumnStart: !0,
		fontWeight: !0,
		lineClamp: !0,
		lineHeight: !0,
		opacity: !0,
		order: !0,
		orphans: !0,
		tabSize: !0,
		widows: !0,
		zIndex: !0,
		zoom: !0,
		fillOpacity: !0,
		floodOpacity: !0,
		stopOpacity: !0,
		strokeDasharray: !0,
		strokeDashoffset: !0,
		strokeMiterlimit: !0,
		strokeOpacity: !0,
		strokeWidth: !0,
	},
	Vc = ["Webkit", "ms", "Moz", "O"];
Object.keys(Rn).forEach((e) => {
	Vc.forEach((t) => {
		(t = t + e.charAt(0).toUpperCase() + e.substring(1)), (Rn[t] = Rn[e]);
	});
});
function Su(e, t, n) {
	return t == null || typeof t == "boolean" || t === ""
		? ""
		: n || typeof t != "number" || t === 0 || (Object.hasOwn(Rn, e) && Rn[e])
			? ("" + t).trim()
			: t + "px";
}
function ku(e, t) {
	e = e.style;
	for (var n in t)
		if (Object.hasOwn(t, n)) {
			var r = n.indexOf("--") === 0,
				l = Su(n, t[n], r);
			n === "float" && (n = "cssFloat"), r ? e.setProperty(n, l) : (e[n] = l);
		}
}
var Hc = Y(
	{ menuitem: !0 },
	{
		area: !0,
		base: !0,
		br: !0,
		col: !0,
		embed: !0,
		hr: !0,
		img: !0,
		input: !0,
		keygen: !0,
		link: !0,
		meta: !0,
		param: !0,
		source: !0,
		track: !0,
		wbr: !0,
	},
);
function ui(e, t) {
	if (t) {
		if (Hc[e] && (t.children != null || t.dangerouslySetInnerHTML != null))
			throw Error(w(137, e));
		if (t.dangerouslySetInnerHTML != null) {
			if (t.children != null) throw Error(w(60));
			if (
				typeof t.dangerouslySetInnerHTML != "object" ||
				!("__html" in t.dangerouslySetInnerHTML)
			)
				throw Error(w(61));
		}
		if (t.style != null && typeof t.style != "object") throw Error(w(62));
	}
}
function ai(e, t) {
	if (e.indexOf("-") === -1) return typeof t.is == "string";
	switch (e) {
		case "annotation-xml":
		case "color-profile":
		case "font-face":
		case "font-face-src":
		case "font-face-uri":
		case "font-face-format":
		case "font-face-name":
		case "missing-glyph":
			return !1;
		default:
			return !0;
	}
}
var ci = null;
function eo(e) {
	return (
		(e = e.target || e.srcElement || window),
		e.correspondingUseElement && (e = e.correspondingUseElement),
		e.nodeType === 3 ? e.parentNode : e
	);
}
var di = null,
	nn = null,
	rn = null;
function Xo(e) {
	if ((e = sr(e))) {
		if (typeof di != "function") throw Error(w(280));
		var t = e.stateNode;
		t && ((t = pl(t)), di(e.stateNode, e.type, t));
	}
}
function xu(e) {
	nn ? (rn ? rn.push(e) : (rn = [e])) : (nn = e);
}
function Nu() {
	if (nn) {
		var e = nn,
			t = rn;
		if (((rn = nn = null), Xo(e), t)) for (e = 0; e < t.length; e++) Xo(t[e]);
	}
}
function Eu(e, t) {
	return e(t);
}
function Cu() {}
var Pl = !1;
function _u(e, t, n) {
	if (Pl) return e(t, n);
	Pl = !0;
	try {
		return Eu(e, t, n);
	} finally {
		(Pl = !1), (nn !== null || rn !== null) && (Cu(), Nu());
	}
}
function Vn(e, t) {
	var n = e.stateNode;
	if (n === null) return null;
	var r = pl(n);
	if (r === null) return null;
	n = r[t];
	switch (t) {
		case "onClick":
		case "onClickCapture":
		case "onDoubleClick":
		case "onDoubleClickCapture":
		case "onMouseDown":
		case "onMouseDownCapture":
		case "onMouseMove":
		case "onMouseMoveCapture":
		case "onMouseUp":
		case "onMouseUpCapture":
		case "onMouseEnter":
			(r = !r.disabled) ||
				((e = e.type),
				(r = !(
					e === "button" ||
					e === "input" ||
					e === "select" ||
					e === "textarea"
				))),
				(e = !r);
			break;
		default:
			e = !1;
	}
	if (e) return null;
	if (n && typeof n != "function") throw Error(w(231, t, typeof n));
	return n;
}
var fi = !1;
if (be)
	try {
		var kn = {};
		Object.defineProperty(kn, "passive", {
			get: () => {
				fi = !0;
			},
		}),
			window.addEventListener("test", kn, kn),
			window.removeEventListener("test", kn, kn);
	} catch {
		fi = !1;
	}
function Kc(e, t, n, r, l, i, o, s, u) {
	var f = Array.prototype.slice.call(arguments, 3);
	try {
		t.apply(n, f);
	} catch (v) {
		this.onError(v);
	}
}
var On = !1,
	Ur = null,
	$r = !1,
	pi = null,
	Qc = {
		onError: (e) => {
			(On = !0), (Ur = e);
		},
	};
function Yc(e, t, n, r, l, i, o, s, u) {
	(On = !1), (Ur = null), Kc.apply(Qc, arguments);
}
function Gc(e, t, n, r, l, i, o, s, u) {
	if ((Yc.apply(this, arguments), On)) {
		if (On) {
			var f = Ur;
			(On = !1), (Ur = null);
		} else throw Error(w(198));
		$r || (($r = !0), (pi = f));
	}
}
function Ut(e) {
	var t = e,
		n = e;
	if (e.alternate) for (; t.return; ) t = t.return;
	else {
		e = t;
		do (t = e), t.flags & 4098 && (n = t.return), (e = t.return);
		while (e);
	}
	return t.tag === 3 ? n : null;
}
function ju(e) {
	if (e.tag === 13) {
		var t = e.memoizedState;
		if (
			(t === null && ((e = e.alternate), e !== null && (t = e.memoizedState)),
			t !== null)
		)
			return t.dehydrated;
	}
	return null;
}
function Zo(e) {
	if (Ut(e) !== e) throw Error(w(188));
}
function Xc(e) {
	var t = e.alternate;
	if (!t) {
		if (((t = Ut(e)), t === null)) throw Error(w(188));
		return t !== e ? null : e;
	}
	for (var n = e, r = t; ; ) {
		var l = n.return;
		if (l === null) break;
		var i = l.alternate;
		if (i === null) {
			if (((r = l.return), r !== null)) {
				n = r;
				continue;
			}
			break;
		}
		if (l.child === i.child) {
			for (i = l.child; i; ) {
				if (i === n) return Zo(l), e;
				if (i === r) return Zo(l), t;
				i = i.sibling;
			}
			throw Error(w(188));
		}
		if (n.return !== r.return) (n = l), (r = i);
		else {
			for (var o = !1, s = l.child; s; ) {
				if (s === n) {
					(o = !0), (n = l), (r = i);
					break;
				}
				if (s === r) {
					(o = !0), (r = l), (n = i);
					break;
				}
				s = s.sibling;
			}
			if (!o) {
				for (s = i.child; s; ) {
					if (s === n) {
						(o = !0), (n = i), (r = l);
						break;
					}
					if (s === r) {
						(o = !0), (r = i), (n = l);
						break;
					}
					s = s.sibling;
				}
				if (!o) throw Error(w(189));
			}
		}
		if (n.alternate !== r) throw Error(w(190));
	}
	if (n.tag !== 3) throw Error(w(188));
	return n.stateNode.current === n ? e : t;
}
function Pu(e) {
	return (e = Xc(e)), e !== null ? Tu(e) : null;
}
function Tu(e) {
	if (e.tag === 5 || e.tag === 6) return e;
	for (e = e.child; e !== null; ) {
		var t = Tu(e);
		if (t !== null) return t;
		e = e.sibling;
	}
	return null;
}
var Lu = Ce.unstable_scheduleCallback,
	Jo = Ce.unstable_cancelCallback,
	Zc = Ce.unstable_shouldYield,
	Jc = Ce.unstable_requestPaint,
	J = Ce.unstable_now,
	qc = Ce.unstable_getCurrentPriorityLevel,
	to = Ce.unstable_ImmediatePriority,
	zu = Ce.unstable_UserBlockingPriority,
	Wr = Ce.unstable_NormalPriority,
	bc = Ce.unstable_LowPriority,
	Ru = Ce.unstable_IdlePriority,
	al = null,
	Ke = null;
function ed(e) {
	if (Ke && typeof Ke.onCommitFiberRoot == "function")
		try {
			Ke.onCommitFiberRoot(al, e, void 0, (e.current.flags & 128) === 128);
		} catch {}
}
var Ae = Math.clz32 ? Math.clz32 : rd,
	td = Math.log,
	nd = Math.LN2;
function rd(e) {
	return (e >>>= 0), e === 0 ? 32 : (31 - ((td(e) / nd) | 0)) | 0;
}
var pr = 64,
	hr = 4194304;
function Ln(e) {
	switch (e & -e) {
		case 1:
			return 1;
		case 2:
			return 2;
		case 4:
			return 4;
		case 8:
			return 8;
		case 16:
			return 16;
		case 32:
			return 32;
		case 64:
		case 128:
		case 256:
		case 512:
		case 1024:
		case 2048:
		case 4096:
		case 8192:
		case 16384:
		case 32768:
		case 65536:
		case 131072:
		case 262144:
		case 524288:
		case 1048576:
		case 2097152:
			return e & 4194240;
		case 4194304:
		case 8388608:
		case 16777216:
		case 33554432:
		case 67108864:
			return e & 130023424;
		case 134217728:
			return 134217728;
		case 268435456:
			return 268435456;
		case 536870912:
			return 536870912;
		case 1073741824:
			return 1073741824;
		default:
			return e;
	}
}
function Br(e, t) {
	var n = e.pendingLanes;
	if (n === 0) return 0;
	var r = 0,
		l = e.suspendedLanes,
		i = e.pingedLanes,
		o = n & 268435455;
	if (o !== 0) {
		var s = o & ~l;
		s !== 0 ? (r = Ln(s)) : ((i &= o), i !== 0 && (r = Ln(i)));
	} else (o = n & ~l), o !== 0 ? (r = Ln(o)) : i !== 0 && (r = Ln(i));
	if (r === 0) return 0;
	if (
		t !== 0 &&
		t !== r &&
		!(t & l) &&
		((l = r & -r), (i = t & -t), l >= i || (l === 16 && (i & 4194240) !== 0))
	)
		return t;
	if ((r & 4 && (r |= n & 16), (t = e.entangledLanes), t !== 0))
		for (e = e.entanglements, t &= r; 0 < t; )
			(n = 31 - Ae(t)), (l = 1 << n), (r |= e[n]), (t &= ~l);
	return r;
}
function ld(e, t) {
	switch (e) {
		case 1:
		case 2:
		case 4:
			return t + 250;
		case 8:
		case 16:
		case 32:
		case 64:
		case 128:
		case 256:
		case 512:
		case 1024:
		case 2048:
		case 4096:
		case 8192:
		case 16384:
		case 32768:
		case 65536:
		case 131072:
		case 262144:
		case 524288:
		case 1048576:
		case 2097152:
			return t + 5e3;
		case 4194304:
		case 8388608:
		case 16777216:
		case 33554432:
		case 67108864:
			return -1;
		case 134217728:
		case 268435456:
		case 536870912:
		case 1073741824:
			return -1;
		default:
			return -1;
	}
}
function id(e, t) {
	for (
		var n = e.suspendedLanes,
			r = e.pingedLanes,
			l = e.expirationTimes,
			i = e.pendingLanes;
		0 < i;
	) {
		var o = 31 - Ae(i),
			s = 1 << o,
			u = l[o];
		u === -1
			? (!(s & n) || s & r) && (l[o] = ld(s, t))
			: u <= t && (e.expiredLanes |= s),
			(i &= ~s);
	}
}
function hi(e) {
	return (
		(e = e.pendingLanes & -1073741825),
		e !== 0 ? e : e & 1073741824 ? 1073741824 : 0
	);
}
function Ou() {
	var e = pr;
	return (pr <<= 1), !(pr & 4194240) && (pr = 64), e;
}
function Tl(e) {
	for (var t = [], n = 0; 31 > n; n++) t.push(e);
	return t;
}
function ir(e, t, n) {
	(e.pendingLanes |= t),
		t !== 536870912 && ((e.suspendedLanes = 0), (e.pingedLanes = 0)),
		(e = e.eventTimes),
		(t = 31 - Ae(t)),
		(e[t] = n);
}
function od(e, t) {
	var n = e.pendingLanes & ~t;
	(e.pendingLanes = t),
		(e.suspendedLanes = 0),
		(e.pingedLanes = 0),
		(e.expiredLanes &= t),
		(e.mutableReadLanes &= t),
		(e.entangledLanes &= t),
		(t = e.entanglements);
	var r = e.eventTimes;
	for (e = e.expirationTimes; 0 < n; ) {
		var l = 31 - Ae(n),
			i = 1 << l;
		(t[l] = 0), (r[l] = -1), (e[l] = -1), (n &= ~i);
	}
}
function no(e, t) {
	var n = (e.entangledLanes |= t);
	for (e = e.entanglements; n; ) {
		var r = 31 - Ae(n),
			l = 1 << r;
		(l & t) | (e[r] & t) && (e[r] |= t), (n &= ~l);
	}
}
var A = 0;
function Du(e) {
	return (e &= -e), 1 < e ? (4 < e ? (e & 268435455 ? 16 : 536870912) : 4) : 1;
}
var Iu,
	ro,
	Fu,
	Mu,
	Au,
	mi = !1,
	mr = [],
	dt = null,
	ft = null,
	pt = null,
	Hn = new Map(),
	Kn = new Map(),
	st = [],
	sd =
		"mousedown mouseup touchcancel touchend touchstart auxclick dblclick pointercancel pointerdown pointerup dragend dragstart drop compositionend compositionstart keydown keypress keyup input textInput copy cut paste click change contextmenu reset submit".split(
			" ",
		);
function qo(e, t) {
	switch (e) {
		case "focusin":
		case "focusout":
			dt = null;
			break;
		case "dragenter":
		case "dragleave":
			ft = null;
			break;
		case "mouseover":
		case "mouseout":
			pt = null;
			break;
		case "pointerover":
		case "pointerout":
			Hn.delete(t.pointerId);
			break;
		case "gotpointercapture":
		case "lostpointercapture":
			Kn.delete(t.pointerId);
	}
}
function xn(e, t, n, r, l, i) {
	return e === null || e.nativeEvent !== i
		? ((e = {
				blockedOn: t,
				domEventName: n,
				eventSystemFlags: r,
				nativeEvent: i,
				targetContainers: [l],
			}),
			t !== null && ((t = sr(t)), t !== null && ro(t)),
			e)
		: ((e.eventSystemFlags |= r),
			(t = e.targetContainers),
			l !== null && t.indexOf(l) === -1 && t.push(l),
			e);
}
function ud(e, t, n, r, l) {
	switch (t) {
		case "focusin":
			return (dt = xn(dt, e, t, n, r, l)), !0;
		case "dragenter":
			return (ft = xn(ft, e, t, n, r, l)), !0;
		case "mouseover":
			return (pt = xn(pt, e, t, n, r, l)), !0;
		case "pointerover": {
			var i = l.pointerId;
			return Hn.set(i, xn(Hn.get(i) || null, e, t, n, r, l)), !0;
		}
		case "gotpointercapture":
			return (
				(i = l.pointerId), Kn.set(i, xn(Kn.get(i) || null, e, t, n, r, l)), !0
			);
	}
	return !1;
}
function Uu(e) {
	var t = Pt(e.target);
	if (t !== null) {
		var n = Ut(t);
		if (n !== null) {
			if (((t = n.tag), t === 13)) {
				if (((t = ju(n)), t !== null)) {
					(e.blockedOn = t),
						Au(e.priority, () => {
							Fu(n);
						});
					return;
				}
			} else if (t === 3 && n.stateNode.current.memoizedState.isDehydrated) {
				e.blockedOn = n.tag === 3 ? n.stateNode.containerInfo : null;
				return;
			}
		}
	}
	e.blockedOn = null;
}
function Pr(e) {
	if (e.blockedOn !== null) return !1;
	for (var t = e.targetContainers; 0 < t.length; ) {
		var n = vi(e.domEventName, e.eventSystemFlags, t[0], e.nativeEvent);
		if (n === null) {
			n = e.nativeEvent;
			var r = new n.constructor(n.type, n);
			(ci = r), n.target.dispatchEvent(r), (ci = null);
		} else return (t = sr(n)), t !== null && ro(t), (e.blockedOn = n), !1;
		t.shift();
	}
	return !0;
}
function bo(e, t, n) {
	Pr(e) && n.delete(t);
}
function ad() {
	(mi = !1),
		dt !== null && Pr(dt) && (dt = null),
		ft !== null && Pr(ft) && (ft = null),
		pt !== null && Pr(pt) && (pt = null),
		Hn.forEach(bo),
		Kn.forEach(bo);
}
function Nn(e, t) {
	e.blockedOn === t &&
		((e.blockedOn = null),
		mi ||
			((mi = !0),
			Ce.unstable_scheduleCallback(Ce.unstable_NormalPriority, ad)));
}
function Qn(e) {
	function t(l) {
		return Nn(l, e);
	}
	if (0 < mr.length) {
		Nn(mr[0], e);
		for (var n = 1; n < mr.length; n++) {
			var r = mr[n];
			r.blockedOn === e && (r.blockedOn = null);
		}
	}
	for (
		dt !== null && Nn(dt, e),
			ft !== null && Nn(ft, e),
			pt !== null && Nn(pt, e),
			Hn.forEach(t),
			Kn.forEach(t),
			n = 0;
		n < st.length;
		n++
	)
		(r = st[n]), r.blockedOn === e && (r.blockedOn = null);
	for (; 0 < st.length && ((n = st[0]), n.blockedOn === null); )
		Uu(n), n.blockedOn === null && st.shift();
}
var ln = rt.ReactCurrentBatchConfig,
	Vr = !0;
function cd(e, t, n, r) {
	var l = A,
		i = ln.transition;
	ln.transition = null;
	try {
		(A = 1), lo(e, t, n, r);
	} finally {
		(A = l), (ln.transition = i);
	}
}
function dd(e, t, n, r) {
	var l = A,
		i = ln.transition;
	ln.transition = null;
	try {
		(A = 4), lo(e, t, n, r);
	} finally {
		(A = l), (ln.transition = i);
	}
}
function lo(e, t, n, r) {
	if (Vr) {
		var l = vi(e, t, n, r);
		if (l === null) Ul(e, t, r, Hr, n), qo(e, r);
		else if (ud(l, e, t, n, r)) r.stopPropagation();
		else if ((qo(e, r), t & 4 && -1 < sd.indexOf(e))) {
			for (; l !== null; ) {
				var i = sr(l);
				if (
					(i !== null && Iu(i),
					(i = vi(e, t, n, r)),
					i === null && Ul(e, t, r, Hr, n),
					i === l)
				)
					break;
				l = i;
			}
			l !== null && r.stopPropagation();
		} else Ul(e, t, r, null, n);
	}
}
var Hr = null;
function vi(e, t, n, r) {
	if (((Hr = null), (e = eo(r)), (e = Pt(e)), e !== null))
		if (((t = Ut(e)), t === null)) e = null;
		else if (((n = t.tag), n === 13)) {
			if (((e = ju(t)), e !== null)) return e;
			e = null;
		} else if (n === 3) {
			if (t.stateNode.current.memoizedState.isDehydrated)
				return t.tag === 3 ? t.stateNode.containerInfo : null;
			e = null;
		} else t !== e && (e = null);
	return (Hr = e), null;
}
function $u(e) {
	switch (e) {
		case "cancel":
		case "click":
		case "close":
		case "contextmenu":
		case "copy":
		case "cut":
		case "auxclick":
		case "dblclick":
		case "dragend":
		case "dragstart":
		case "drop":
		case "focusin":
		case "focusout":
		case "input":
		case "invalid":
		case "keydown":
		case "keypress":
		case "keyup":
		case "mousedown":
		case "mouseup":
		case "paste":
		case "pause":
		case "play":
		case "pointercancel":
		case "pointerdown":
		case "pointerup":
		case "ratechange":
		case "reset":
		case "resize":
		case "seeked":
		case "submit":
		case "touchcancel":
		case "touchend":
		case "touchstart":
		case "volumechange":
		case "change":
		case "selectionchange":
		case "textInput":
		case "compositionstart":
		case "compositionend":
		case "compositionupdate":
		case "beforeblur":
		case "afterblur":
		case "beforeinput":
		case "blur":
		case "fullscreenchange":
		case "focus":
		case "hashchange":
		case "popstate":
		case "select":
		case "selectstart":
			return 1;
		case "drag":
		case "dragenter":
		case "dragexit":
		case "dragleave":
		case "dragover":
		case "mousemove":
		case "mouseout":
		case "mouseover":
		case "pointermove":
		case "pointerout":
		case "pointerover":
		case "scroll":
		case "toggle":
		case "touchmove":
		case "wheel":
		case "mouseenter":
		case "mouseleave":
		case "pointerenter":
		case "pointerleave":
			return 4;
		case "message":
			switch (qc()) {
				case to:
					return 1;
				case zu:
					return 4;
				case Wr:
				case bc:
					return 16;
				case Ru:
					return 536870912;
				default:
					return 16;
			}
		default:
			return 16;
	}
}
var at = null,
	io = null,
	Tr = null;
function Wu() {
	if (Tr) return Tr;
	var e,
		t = io,
		n = t.length,
		r,
		l = "value" in at ? at.value : at.textContent,
		i = l.length;
	for (e = 0; e < n && t[e] === l[e]; e++);
	var o = n - e;
	for (r = 1; r <= o && t[n - r] === l[i - r]; r++);
	return (Tr = l.slice(e, 1 < r ? 1 - r : void 0));
}
function Lr(e) {
	var t = e.keyCode;
	return (
		"charCode" in e
			? ((e = e.charCode), e === 0 && t === 13 && (e = 13))
			: (e = t),
		e === 10 && (e = 13),
		32 <= e || e === 13 ? e : 0
	);
}
function vr() {
	return !0;
}
function es() {
	return !1;
}
function je(e) {
	function t(n, r, l, i, o) {
		(this._reactName = n),
			(this._targetInst = l),
			(this.type = r),
			(this.nativeEvent = i),
			(this.target = o),
			(this.currentTarget = null);
		for (var s in e)
			Object.hasOwn(e, s) && ((n = e[s]), (this[s] = n ? n(i) : i[s]));
		return (
			(this.isDefaultPrevented = (
				i.defaultPrevented != null
					? i.defaultPrevented
					: i.returnValue === !1
			)
				? vr
				: es),
			(this.isPropagationStopped = es),
			this
		);
	}
	return (
		Y(t.prototype, {
			preventDefault: function () {
				this.defaultPrevented = !0;
				var n = this.nativeEvent;
				n &&
					(n.preventDefault
						? n.preventDefault()
						: typeof n.returnValue != "unknown" && (n.returnValue = !1),
					(this.isDefaultPrevented = vr));
			},
			stopPropagation: function () {
				var n = this.nativeEvent;
				n &&
					(n.stopPropagation
						? n.stopPropagation()
						: typeof n.cancelBubble != "unknown" && (n.cancelBubble = !0),
					(this.isPropagationStopped = vr));
			},
			persist: () => {},
			isPersistent: vr,
		}),
		t
	);
}
var vn = {
		eventPhase: 0,
		bubbles: 0,
		cancelable: 0,
		timeStamp: (e) => e.timeStamp || Date.now(),
		defaultPrevented: 0,
		isTrusted: 0,
	},
	oo = je(vn),
	or = Y({}, vn, { view: 0, detail: 0 }),
	fd = je(or),
	Ll,
	zl,
	En,
	cl = Y({}, or, {
		screenX: 0,
		screenY: 0,
		clientX: 0,
		clientY: 0,
		pageX: 0,
		pageY: 0,
		ctrlKey: 0,
		shiftKey: 0,
		altKey: 0,
		metaKey: 0,
		getModifierState: so,
		button: 0,
		buttons: 0,
		relatedTarget: (e) =>
			e.relatedTarget === void 0
				? e.fromElement === e.srcElement
					? e.toElement
					: e.fromElement
				: e.relatedTarget,
		movementX: (e) =>
			"movementX" in e
				? e.movementX
				: (e !== En &&
						(En && e.type === "mousemove"
							? ((Ll = e.screenX - En.screenX), (zl = e.screenY - En.screenY))
							: (zl = Ll = 0),
						(En = e)),
					Ll),
		movementY: (e) => ("movementY" in e ? e.movementY : zl),
	}),
	ts = je(cl),
	pd = Y({}, cl, { dataTransfer: 0 }),
	hd = je(pd),
	md = Y({}, or, { relatedTarget: 0 }),
	Rl = je(md),
	vd = Y({}, vn, { animationName: 0, elapsedTime: 0, pseudoElement: 0 }),
	yd = je(vd),
	gd = Y({}, vn, {
		clipboardData: (e) =>
			"clipboardData" in e ? e.clipboardData : window.clipboardData,
	}),
	wd = je(gd),
	Sd = Y({}, vn, { data: 0 }),
	ns = je(Sd),
	kd = {
		Esc: "Escape",
		Spacebar: " ",
		Left: "ArrowLeft",
		Up: "ArrowUp",
		Right: "ArrowRight",
		Down: "ArrowDown",
		Del: "Delete",
		Win: "OS",
		Menu: "ContextMenu",
		Apps: "ContextMenu",
		Scroll: "ScrollLock",
		MozPrintableKey: "Unidentified",
	},
	xd = {
		8: "Backspace",
		9: "Tab",
		12: "Clear",
		13: "Enter",
		16: "Shift",
		17: "Control",
		18: "Alt",
		19: "Pause",
		20: "CapsLock",
		27: "Escape",
		32: " ",
		33: "PageUp",
		34: "PageDown",
		35: "End",
		36: "Home",
		37: "ArrowLeft",
		38: "ArrowUp",
		39: "ArrowRight",
		40: "ArrowDown",
		45: "Insert",
		46: "Delete",
		112: "F1",
		113: "F2",
		114: "F3",
		115: "F4",
		116: "F5",
		117: "F6",
		118: "F7",
		119: "F8",
		120: "F9",
		121: "F10",
		122: "F11",
		123: "F12",
		144: "NumLock",
		145: "ScrollLock",
		224: "Meta",
	},
	Nd = {
		Alt: "altKey",
		Control: "ctrlKey",
		Meta: "metaKey",
		Shift: "shiftKey",
	};
function Ed(e) {
	var t = this.nativeEvent;
	return t.getModifierState ? t.getModifierState(e) : (e = Nd[e]) ? !!t[e] : !1;
}
function so() {
	return Ed;
}
var Cd = Y({}, or, {
		key: (e) => {
			if (e.key) {
				var t = kd[e.key] || e.key;
				if (t !== "Unidentified") return t;
			}
			return e.type === "keypress"
				? ((e = Lr(e)), e === 13 ? "Enter" : String.fromCharCode(e))
				: e.type === "keydown" || e.type === "keyup"
					? xd[e.keyCode] || "Unidentified"
					: "";
		},
		code: 0,
		location: 0,
		ctrlKey: 0,
		shiftKey: 0,
		altKey: 0,
		metaKey: 0,
		repeat: 0,
		locale: 0,
		getModifierState: so,
		charCode: (e) => (e.type === "keypress" ? Lr(e) : 0),
		keyCode: (e) =>
			e.type === "keydown" || e.type === "keyup" ? e.keyCode : 0,
		which: (e) =>
			e.type === "keypress"
				? Lr(e)
				: e.type === "keydown" || e.type === "keyup"
					? e.keyCode
					: 0,
	}),
	_d = je(Cd),
	jd = Y({}, cl, {
		pointerId: 0,
		width: 0,
		height: 0,
		pressure: 0,
		tangentialPressure: 0,
		tiltX: 0,
		tiltY: 0,
		twist: 0,
		pointerType: 0,
		isPrimary: 0,
	}),
	rs = je(jd),
	Pd = Y({}, or, {
		touches: 0,
		targetTouches: 0,
		changedTouches: 0,
		altKey: 0,
		metaKey: 0,
		ctrlKey: 0,
		shiftKey: 0,
		getModifierState: so,
	}),
	Td = je(Pd),
	Ld = Y({}, vn, { propertyName: 0, elapsedTime: 0, pseudoElement: 0 }),
	zd = je(Ld),
	Rd = Y({}, cl, {
		deltaX: (e) =>
			"deltaX" in e ? e.deltaX : "wheelDeltaX" in e ? -e.wheelDeltaX : 0,
		deltaY: (e) =>
			"deltaY" in e
				? e.deltaY
				: "wheelDeltaY" in e
					? -e.wheelDeltaY
					: "wheelDelta" in e
						? -e.wheelDelta
						: 0,
		deltaZ: 0,
		deltaMode: 0,
	}),
	Od = je(Rd),
	Dd = [9, 13, 27, 32],
	uo = be && "CompositionEvent" in window,
	Dn = null;
be && "documentMode" in document && (Dn = document.documentMode);
var Id = be && "TextEvent" in window && !Dn,
	Bu = be && (!uo || (Dn && 8 < Dn && 11 >= Dn)),
	ls = String.fromCharCode(32),
	is = !1;
function Vu(e, t) {
	switch (e) {
		case "keyup":
			return Dd.indexOf(t.keyCode) !== -1;
		case "keydown":
			return t.keyCode !== 229;
		case "keypress":
		case "mousedown":
		case "focusout":
			return !0;
		default:
			return !1;
	}
}
function Hu(e) {
	return (e = e.detail), typeof e == "object" && "data" in e ? e.data : null;
}
var Kt = !1;
function Fd(e, t) {
	switch (e) {
		case "compositionend":
			return Hu(t);
		case "keypress":
			return t.which !== 32 ? null : ((is = !0), ls);
		case "textInput":
			return (e = t.data), e === ls && is ? null : e;
		default:
			return null;
	}
}
function Md(e, t) {
	if (Kt)
		return e === "compositionend" || (!uo && Vu(e, t))
			? ((e = Wu()), (Tr = io = at = null), (Kt = !1), e)
			: null;
	switch (e) {
		case "paste":
			return null;
		case "keypress":
			if (!(t.ctrlKey || t.altKey || t.metaKey) || (t.ctrlKey && t.altKey)) {
				if (t.char && 1 < t.char.length) return t.char;
				if (t.which) return String.fromCharCode(t.which);
			}
			return null;
		case "compositionend":
			return Bu && t.locale !== "ko" ? null : t.data;
		default:
			return null;
	}
}
var Ad = {
	color: !0,
	date: !0,
	datetime: !0,
	"datetime-local": !0,
	email: !0,
	month: !0,
	number: !0,
	password: !0,
	range: !0,
	search: !0,
	tel: !0,
	text: !0,
	time: !0,
	url: !0,
	week: !0,
};
function os(e) {
	var t = e && e.nodeName && e.nodeName.toLowerCase();
	return t === "input" ? !!Ad[e.type] : t === "textarea";
}
function Ku(e, t, n, r) {
	xu(r),
		(t = Kr(t, "onChange")),
		0 < t.length &&
			((n = new oo("onChange", "change", null, n, r)),
			e.push({ event: n, listeners: t }));
}
var In = null,
	Yn = null;
function Ud(e) {
	na(e, 0);
}
function dl(e) {
	var t = Gt(e);
	if (mu(t)) return e;
}
function $d(e, t) {
	if (e === "change") return t;
}
var Qu = !1;
if (be) {
	var Ol;
	if (be) {
		var Dl = "oninput" in document;
		if (!Dl) {
			var ss = document.createElement("div");
			ss.setAttribute("oninput", "return;"),
				(Dl = typeof ss.oninput == "function");
		}
		Ol = Dl;
	} else Ol = !1;
	Qu = Ol && (!document.documentMode || 9 < document.documentMode);
}
function us() {
	In && (In.detachEvent("onpropertychange", Yu), (Yn = In = null));
}
function Yu(e) {
	if (e.propertyName === "value" && dl(Yn)) {
		var t = [];
		Ku(t, Yn, e, eo(e)), _u(Ud, t);
	}
}
function Wd(e, t, n) {
	e === "focusin"
		? (us(), (In = t), (Yn = n), In.attachEvent("onpropertychange", Yu))
		: e === "focusout" && us();
}
function Bd(e) {
	if (e === "selectionchange" || e === "keyup" || e === "keydown")
		return dl(Yn);
}
function Vd(e, t) {
	if (e === "click") return dl(t);
}
function Hd(e, t) {
	if (e === "input" || e === "change") return dl(t);
}
function Kd(e, t) {
	return (e === t && (e !== 0 || 1 / e === 1 / t)) || (e !== e && t !== t);
}
var $e = typeof Object.is == "function" ? Object.is : Kd;
function Gn(e, t) {
	if ($e(e, t)) return !0;
	if (typeof e != "object" || e === null || typeof t != "object" || t === null)
		return !1;
	var n = Object.keys(e),
		r = Object.keys(t);
	if (n.length !== r.length) return !1;
	for (r = 0; r < n.length; r++) {
		var l = n[r];
		if (!ql.call(t, l) || !$e(e[l], t[l])) return !1;
	}
	return !0;
}
function as(e) {
	for (; e && e.firstChild; ) e = e.firstChild;
	return e;
}
function cs(e, t) {
	var n = as(e);
	e = 0;
	for (var r; n; ) {
		if (n.nodeType === 3) {
			if (((r = e + n.textContent.length), e <= t && r >= t))
				return { node: n, offset: t - e };
			e = r;
		}
		e: {
			for (; n; ) {
				if (n.nextSibling) {
					n = n.nextSibling;
					break e;
				}
				n = n.parentNode;
			}
			n = void 0;
		}
		n = as(n);
	}
}
function Gu(e, t) {
	return e && t
		? e === t
			? !0
			: e && e.nodeType === 3
				? !1
				: t && t.nodeType === 3
					? Gu(e, t.parentNode)
					: "contains" in e
						? e.contains(t)
						: e.compareDocumentPosition
							? !!(e.compareDocumentPosition(t) & 16)
							: !1
		: !1;
}
function Xu() {
	for (var e = window, t = Ar(); t instanceof e.HTMLIFrameElement; ) {
		try {
			var n = typeof t.contentWindow.location.href == "string";
		} catch {
			n = !1;
		}
		if (n) e = t.contentWindow;
		else break;
		t = Ar(e.document);
	}
	return t;
}
function ao(e) {
	var t = e && e.nodeName && e.nodeName.toLowerCase();
	return (
		t &&
		((t === "input" &&
			(e.type === "text" ||
				e.type === "search" ||
				e.type === "tel" ||
				e.type === "url" ||
				e.type === "password")) ||
			t === "textarea" ||
			e.contentEditable === "true")
	);
}
function Qd(e) {
	var t = Xu(),
		n = e.focusedElem,
		r = e.selectionRange;
	if (
		t !== n &&
		n &&
		n.ownerDocument &&
		Gu(n.ownerDocument.documentElement, n)
	) {
		if (r !== null && ao(n)) {
			if (
				((t = r.start),
				(e = r.end),
				e === void 0 && (e = t),
				"selectionStart" in n)
			)
				(n.selectionStart = t), (n.selectionEnd = Math.min(e, n.value.length));
			else if (
				((e = ((t = n.ownerDocument || document) && t.defaultView) || window),
				e.getSelection)
			) {
				e = e.getSelection();
				var l = n.textContent.length,
					i = Math.min(r.start, l);
				(r = r.end === void 0 ? i : Math.min(r.end, l)),
					!e.extend && i > r && ((l = r), (r = i), (i = l)),
					(l = cs(n, i));
				var o = cs(n, r);
				l &&
					o &&
					(e.rangeCount !== 1 ||
						e.anchorNode !== l.node ||
						e.anchorOffset !== l.offset ||
						e.focusNode !== o.node ||
						e.focusOffset !== o.offset) &&
					((t = t.createRange()),
					t.setStart(l.node, l.offset),
					e.removeAllRanges(),
					i > r
						? (e.addRange(t), e.extend(o.node, o.offset))
						: (t.setEnd(o.node, o.offset), e.addRange(t)));
			}
		}
		for (t = [], e = n; (e = e.parentNode); )
			e.nodeType === 1 &&
				t.push({ element: e, left: e.scrollLeft, top: e.scrollTop });
		for (typeof n.focus == "function" && n.focus(), n = 0; n < t.length; n++)
			(e = t[n]),
				(e.element.scrollLeft = e.left),
				(e.element.scrollTop = e.top);
	}
}
var Yd = be && "documentMode" in document && 11 >= document.documentMode,
	Qt = null,
	yi = null,
	Fn = null,
	gi = !1;
function ds(e, t, n) {
	var r = n.window === n ? n.document : n.nodeType === 9 ? n : n.ownerDocument;
	gi ||
		Qt == null ||
		Qt !== Ar(r) ||
		((r = Qt),
		"selectionStart" in r && ao(r)
			? (r = { start: r.selectionStart, end: r.selectionEnd })
			: ((r = (
					(r.ownerDocument && r.ownerDocument.defaultView) ||
					window
				).getSelection()),
				(r = {
					anchorNode: r.anchorNode,
					anchorOffset: r.anchorOffset,
					focusNode: r.focusNode,
					focusOffset: r.focusOffset,
				})),
		(Fn && Gn(Fn, r)) ||
			((Fn = r),
			(r = Kr(yi, "onSelect")),
			0 < r.length &&
				((t = new oo("onSelect", "select", null, t, n)),
				e.push({ event: t, listeners: r }),
				(t.target = Qt))));
}
function yr(e, t) {
	var n = {};
	return (
		(n[e.toLowerCase()] = t.toLowerCase()),
		(n["Webkit" + e] = "webkit" + t),
		(n["Moz" + e] = "moz" + t),
		n
	);
}
var Yt = {
		animationend: yr("Animation", "AnimationEnd"),
		animationiteration: yr("Animation", "AnimationIteration"),
		animationstart: yr("Animation", "AnimationStart"),
		transitionend: yr("Transition", "TransitionEnd"),
	},
	Il = {},
	Zu = {};
be &&
	((Zu = document.createElement("div").style),
	"AnimationEvent" in window ||
		(delete Yt.animationend.animation,
		delete Yt.animationiteration.animation,
		delete Yt.animationstart.animation),
	"TransitionEvent" in window || delete Yt.transitionend.transition);
function fl(e) {
	if (Il[e]) return Il[e];
	if (!Yt[e]) return e;
	var t = Yt[e],
		n;
	for (n in t) if (Object.hasOwn(t, n) && n in Zu) return (Il[e] = t[n]);
	return e;
}
var Ju = fl("animationend"),
	qu = fl("animationiteration"),
	bu = fl("animationstart"),
	ea = fl("transitionend"),
	ta = new Map(),
	fs =
		"abort auxClick cancel canPlay canPlayThrough click close contextMenu copy cut drag dragEnd dragEnter dragExit dragLeave dragOver dragStart drop durationChange emptied encrypted ended error gotPointerCapture input invalid keyDown keyPress keyUp load loadedData loadedMetadata loadStart lostPointerCapture mouseDown mouseMove mouseOut mouseOver mouseUp paste pause play playing pointerCancel pointerDown pointerMove pointerOut pointerOver pointerUp progress rateChange reset resize seeked seeking stalled submit suspend timeUpdate touchCancel touchEnd touchStart volumeChange scroll toggle touchMove waiting wheel".split(
			" ",
		);
function kt(e, t) {
	ta.set(e, t), At(t, [e]);
}
for (var Fl = 0; Fl < fs.length; Fl++) {
	var Ml = fs[Fl],
		Gd = Ml.toLowerCase(),
		Xd = Ml[0].toUpperCase() + Ml.slice(1);
	kt(Gd, "on" + Xd);
}
kt(Ju, "onAnimationEnd");
kt(qu, "onAnimationIteration");
kt(bu, "onAnimationStart");
kt("dblclick", "onDoubleClick");
kt("focusin", "onFocus");
kt("focusout", "onBlur");
kt(ea, "onTransitionEnd");
un("onMouseEnter", ["mouseout", "mouseover"]);
un("onMouseLeave", ["mouseout", "mouseover"]);
un("onPointerEnter", ["pointerout", "pointerover"]);
un("onPointerLeave", ["pointerout", "pointerover"]);
At(
	"onChange",
	"change click focusin focusout input keydown keyup selectionchange".split(
		" ",
	),
);
At(
	"onSelect",
	"focusout contextmenu dragend focusin keydown keyup mousedown mouseup selectionchange".split(
		" ",
	),
);
At("onBeforeInput", ["compositionend", "keypress", "textInput", "paste"]);
At(
	"onCompositionEnd",
	"compositionend focusout keydown keypress keyup mousedown".split(" "),
);
At(
	"onCompositionStart",
	"compositionstart focusout keydown keypress keyup mousedown".split(" "),
);
At(
	"onCompositionUpdate",
	"compositionupdate focusout keydown keypress keyup mousedown".split(" "),
);
var zn =
		"abort canplay canplaythrough durationchange emptied encrypted ended error loadeddata loadedmetadata loadstart pause play playing progress ratechange resize seeked seeking stalled suspend timeupdate volumechange waiting".split(
			" ",
		),
	Zd = new Set("cancel close invalid load scroll toggle".split(" ").concat(zn));
function ps(e, t, n) {
	var r = e.type || "unknown-event";
	(e.currentTarget = n), Gc(r, t, void 0, e), (e.currentTarget = null);
}
function na(e, t) {
	t = (t & 4) !== 0;
	for (var n = 0; n < e.length; n++) {
		var r = e[n],
			l = r.event;
		r = r.listeners;
		e: {
			var i = void 0;
			if (t)
				for (var o = r.length - 1; 0 <= o; o--) {
					var s = r[o],
						u = s.instance,
						f = s.currentTarget;
					if (((s = s.listener), u !== i && l.isPropagationStopped())) break e;
					ps(l, s, f), (i = u);
				}
			else
				for (o = 0; o < r.length; o++) {
					if (
						((s = r[o]),
						(u = s.instance),
						(f = s.currentTarget),
						(s = s.listener),
						u !== i && l.isPropagationStopped())
					)
						break e;
					ps(l, s, f), (i = u);
				}
		}
	}
	if ($r) throw ((e = pi), ($r = !1), (pi = null), e);
}
function B(e, t) {
	var n = t[Ni];
	n === void 0 && (n = t[Ni] = new Set());
	var r = e + "__bubble";
	n.has(r) || (ra(t, e, 2, !1), n.add(r));
}
function Al(e, t, n) {
	var r = 0;
	t && (r |= 4), ra(n, e, r, t);
}
var gr = "_reactListening" + Math.random().toString(36).slice(2);
function Xn(e) {
	if (!e[gr]) {
		(e[gr] = !0),
			cu.forEach((n) => {
				n !== "selectionchange" && (Zd.has(n) || Al(n, !1, e), Al(n, !0, e));
			});
		var t = e.nodeType === 9 ? e : e.ownerDocument;
		t === null || t[gr] || ((t[gr] = !0), Al("selectionchange", !1, t));
	}
}
function ra(e, t, n, r) {
	switch ($u(t)) {
		case 1: {
			var l = cd;
			break;
		}
		case 4:
			l = dd;
			break;
		default:
			l = lo;
	}
	(n = l.bind(null, t, n, e)),
		(l = void 0),
		!fi ||
			(t !== "touchstart" && t !== "touchmove" && t !== "wheel") ||
			(l = !0),
		r
			? l !== void 0
				? e.addEventListener(t, n, { capture: !0, passive: l })
				: e.addEventListener(t, n, !0)
			: l !== void 0
				? e.addEventListener(t, n, { passive: l })
				: e.addEventListener(t, n, !1);
}
function Ul(e, t, n, r, l) {
	var i = r;
	if (!(t & 1) && !(t & 2) && r !== null)
		e: for (;;) {
			if (r === null) return;
			var o = r.tag;
			if (o === 3 || o === 4) {
				var s = r.stateNode.containerInfo;
				if (s === l || (s.nodeType === 8 && s.parentNode === l)) break;
				if (o === 4)
					for (o = r.return; o !== null; ) {
						var u = o.tag;
						if (
							(u === 3 || u === 4) &&
							((u = o.stateNode.containerInfo),
							u === l || (u.nodeType === 8 && u.parentNode === l))
						)
							return;
						o = o.return;
					}
				for (; s !== null; ) {
					if (((o = Pt(s)), o === null)) return;
					if (((u = o.tag), u === 5 || u === 6)) {
						r = i = o;
						continue e;
					}
					s = s.parentNode;
				}
			}
			r = r.return;
		}
	_u(() => {
		var f = i,
			v = eo(n),
			h = [];
		e: {
			var m = ta.get(e);
			if (m !== void 0) {
				var g = oo,
					x = e;
				switch (e) {
					case "keypress":
						if (Lr(n) === 0) break e;
					case "keydown":
					case "keyup":
						g = _d;
						break;
					case "focusin":
						(x = "focus"), (g = Rl);
						break;
					case "focusout":
						(x = "blur"), (g = Rl);
						break;
					case "beforeblur":
					case "afterblur":
						g = Rl;
						break;
					case "click":
						if (n.button === 2) break e;
					case "auxclick":
					case "dblclick":
					case "mousedown":
					case "mousemove":
					case "mouseup":
					case "mouseout":
					case "mouseover":
					case "contextmenu":
						g = ts;
						break;
					case "drag":
					case "dragend":
					case "dragenter":
					case "dragexit":
					case "dragleave":
					case "dragover":
					case "dragstart":
					case "drop":
						g = hd;
						break;
					case "touchcancel":
					case "touchend":
					case "touchmove":
					case "touchstart":
						g = Td;
						break;
					case Ju:
					case qu:
					case bu:
						g = yd;
						break;
					case ea:
						g = zd;
						break;
					case "scroll":
						g = fd;
						break;
					case "wheel":
						g = Od;
						break;
					case "copy":
					case "cut":
					case "paste":
						g = wd;
						break;
					case "gotpointercapture":
					case "lostpointercapture":
					case "pointercancel":
					case "pointerdown":
					case "pointermove":
					case "pointerout":
					case "pointerover":
					case "pointerup":
						g = rs;
				}
				var E = (t & 4) !== 0,
					D = !E && e === "scroll",
					p = E ? (m !== null ? m + "Capture" : null) : m;
				E = [];
				for (var a = f, d; a !== null; ) {
					d = a;
					var y = d.stateNode;
					if (
						(d.tag === 5 &&
							y !== null &&
							((d = y),
							p !== null && ((y = Vn(a, p)), y != null && E.push(Zn(a, y, d)))),
						D)
					)
						break;
					a = a.return;
				}
				0 < E.length &&
					((m = new g(m, x, null, n, v)), h.push({ event: m, listeners: E }));
			}
		}
		if (!(t & 7)) {
			e: {
				if (
					((m = e === "mouseover" || e === "pointerover"),
					(g = e === "mouseout" || e === "pointerout"),
					m &&
						n !== ci &&
						(x = n.relatedTarget || n.fromElement) &&
						(Pt(x) || x[et]))
				)
					break e;
				if (
					(g || m) &&
					((m =
						v.window === v
							? v
							: (m = v.ownerDocument)
								? m.defaultView || m.parentWindow
								: window),
					g
						? ((x = n.relatedTarget || n.toElement),
							(g = f),
							(x = x ? Pt(x) : null),
							x !== null &&
								((D = Ut(x)), x !== D || (x.tag !== 5 && x.tag !== 6)) &&
								(x = null))
						: ((g = null), (x = f)),
					g !== x)
				) {
					if (
						((E = ts),
						(y = "onMouseLeave"),
						(p = "onMouseEnter"),
						(a = "mouse"),
						(e === "pointerout" || e === "pointerover") &&
							((E = rs),
							(y = "onPointerLeave"),
							(p = "onPointerEnter"),
							(a = "pointer")),
						(D = g == null ? m : Gt(g)),
						(d = x == null ? m : Gt(x)),
						(m = new E(y, a + "leave", g, n, v)),
						(m.target = D),
						(m.relatedTarget = d),
						(y = null),
						Pt(v) === f &&
							((E = new E(p, a + "enter", x, n, v)),
							(E.target = d),
							(E.relatedTarget = D),
							(y = E)),
						(D = y),
						g && x)
					)
						t: {
							for (E = g, p = x, a = 0, d = E; d; d = Bt(d)) a++;
							for (d = 0, y = p; y; y = Bt(y)) d++;
							for (; 0 < a - d; ) (E = Bt(E)), a--;
							for (; 0 < d - a; ) (p = Bt(p)), d--;
							for (; a--; ) {
								if (E === p || (p !== null && E === p.alternate)) break t;
								(E = Bt(E)), (p = Bt(p));
							}
							E = null;
						}
					else E = null;
					g !== null && hs(h, m, g, E, !1),
						x !== null && D !== null && hs(h, D, x, E, !0);
				}
			}
			e: {
				if (
					((m = f ? Gt(f) : window),
					(g = m.nodeName && m.nodeName.toLowerCase()),
					g === "select" || (g === "input" && m.type === "file"))
				)
					var N = $d;
				else if (os(m))
					if (Qu) N = Hd;
					else {
						N = Bd;
						var k = Wd;
					}
				else
					(g = m.nodeName) &&
						g.toLowerCase() === "input" &&
						(m.type === "checkbox" || m.type === "radio") &&
						(N = Vd);
				if (N && (N = N(e, f))) {
					Ku(h, N, n, v);
					break e;
				}
				k && k(e, m, f),
					e === "focusout" &&
						(k = m._wrapperState) &&
						k.controlled &&
						m.type === "number" &&
						ii(m, "number", m.value);
			}
			switch (((k = f ? Gt(f) : window), e)) {
				case "focusin":
					(os(k) || k.contentEditable === "true") &&
						((Qt = k), (yi = f), (Fn = null));
					break;
				case "focusout":
					Fn = yi = Qt = null;
					break;
				case "mousedown":
					gi = !0;
					break;
				case "contextmenu":
				case "mouseup":
				case "dragend":
					(gi = !1), ds(h, n, v);
					break;
				case "selectionchange":
					if (Yd) break;
				case "keydown":
				case "keyup":
					ds(h, n, v);
			}
			var C;
			if (uo)
				e: {
					switch (e) {
						case "compositionstart": {
							var L = "onCompositionStart";
							break e;
						}
						case "compositionend":
							L = "onCompositionEnd";
							break e;
						case "compositionupdate":
							L = "onCompositionUpdate";
							break e;
					}
					L = void 0;
				}
			else
				Kt
					? Vu(e, n) && (L = "onCompositionEnd")
					: e === "keydown" && n.keyCode === 229 && (L = "onCompositionStart");
			L &&
				(Bu &&
					n.locale !== "ko" &&
					(Kt || L !== "onCompositionStart"
						? L === "onCompositionEnd" && Kt && (C = Wu())
						: ((at = v),
							(io = "value" in at ? at.value : at.textContent),
							(Kt = !0))),
				(k = Kr(f, L)),
				0 < k.length &&
					((L = new ns(L, e, null, n, v)),
					h.push({ event: L, listeners: k }),
					C ? (L.data = C) : ((C = Hu(n)), C !== null && (L.data = C)))),
				(C = Id ? Fd(e, n) : Md(e, n)) &&
					((f = Kr(f, "onBeforeInput")),
					0 < f.length &&
						((v = new ns("onBeforeInput", "beforeinput", null, n, v)),
						h.push({ event: v, listeners: f }),
						(v.data = C)));
		}
		na(h, t);
	});
}
function Zn(e, t, n) {
	return { instance: e, listener: t, currentTarget: n };
}
function Kr(e, t) {
	for (var n = t + "Capture", r = []; e !== null; ) {
		var l = e,
			i = l.stateNode;
		l.tag === 5 &&
			i !== null &&
			((l = i),
			(i = Vn(e, n)),
			i != null && r.unshift(Zn(e, i, l)),
			(i = Vn(e, t)),
			i != null && r.push(Zn(e, i, l))),
			(e = e.return);
	}
	return r;
}
function Bt(e) {
	if (e === null) return null;
	do e = e.return;
	while (e && e.tag !== 5);
	return e || null;
}
function hs(e, t, n, r, l) {
	for (var i = t._reactName, o = []; n !== null && n !== r; ) {
		var s = n,
			u = s.alternate,
			f = s.stateNode;
		if (u !== null && u === r) break;
		s.tag === 5 &&
			f !== null &&
			((s = f),
			l
				? ((u = Vn(n, i)), u != null && o.unshift(Zn(n, u, s)))
				: l || ((u = Vn(n, i)), u != null && o.push(Zn(n, u, s)))),
			(n = n.return);
	}
	o.length !== 0 && e.push({ event: t, listeners: o });
}
var Jd = /\r\n?/g,
	qd = /\u0000|\uFFFD/g;
function ms(e) {
	return (typeof e == "string" ? e : "" + e)
		.replace(
			Jd,
			`
`,
		)
		.replace(qd, "");
}
function wr(e, t, n) {
	if (((t = ms(t)), ms(e) !== t && n)) throw Error(w(425));
}
function Qr() {}
var wi = null,
	Si = null;
function ki(e, t) {
	return (
		e === "textarea" ||
		e === "noscript" ||
		typeof t.children == "string" ||
		typeof t.children == "number" ||
		(typeof t.dangerouslySetInnerHTML == "object" &&
			t.dangerouslySetInnerHTML !== null &&
			t.dangerouslySetInnerHTML.__html != null)
	);
}
var xi = typeof setTimeout == "function" ? setTimeout : void 0,
	bd = typeof clearTimeout == "function" ? clearTimeout : void 0,
	vs = typeof Promise == "function" ? Promise : void 0,
	ef =
		typeof queueMicrotask == "function"
			? queueMicrotask
			: typeof vs < "u"
				? (e) => vs.resolve(null).then(e).catch(tf)
				: xi;
function tf(e) {
	setTimeout(() => {
		throw e;
	});
}
function $l(e, t) {
	var n = t,
		r = 0;
	do {
		var l = n.nextSibling;
		if ((e.removeChild(n), l && l.nodeType === 8))
			if (((n = l.data), n === "/$")) {
				if (r === 0) {
					e.removeChild(l), Qn(t);
					return;
				}
				r--;
			} else (n !== "$" && n !== "$?" && n !== "$!") || r++;
		n = l;
	} while (n);
	Qn(t);
}
function ht(e) {
	for (; e != null; e = e.nextSibling) {
		var t = e.nodeType;
		if (t === 1 || t === 3) break;
		if (t === 8) {
			if (((t = e.data), t === "$" || t === "$!" || t === "$?")) break;
			if (t === "/$") return null;
		}
	}
	return e;
}
function ys(e) {
	e = e.previousSibling;
	for (var t = 0; e; ) {
		if (e.nodeType === 8) {
			var n = e.data;
			if (n === "$" || n === "$!" || n === "$?") {
				if (t === 0) return e;
				t--;
			} else n === "/$" && t++;
		}
		e = e.previousSibling;
	}
	return null;
}
var yn = Math.random().toString(36).slice(2),
	He = "__reactFiber$" + yn,
	Jn = "__reactProps$" + yn,
	et = "__reactContainer$" + yn,
	Ni = "__reactEvents$" + yn,
	nf = "__reactListeners$" + yn,
	rf = "__reactHandles$" + yn;
function Pt(e) {
	var t = e[He];
	if (t) return t;
	for (var n = e.parentNode; n; ) {
		if ((t = n[et] || n[He])) {
			if (
				((n = t.alternate),
				t.child !== null || (n !== null && n.child !== null))
			)
				for (e = ys(e); e !== null; ) {
					if ((n = e[He])) return n;
					e = ys(e);
				}
			return t;
		}
		(e = n), (n = e.parentNode);
	}
	return null;
}
function sr(e) {
	return (
		(e = e[He] || e[et]),
		!e || (e.tag !== 5 && e.tag !== 6 && e.tag !== 13 && e.tag !== 3) ? null : e
	);
}
function Gt(e) {
	if (e.tag === 5 || e.tag === 6) return e.stateNode;
	throw Error(w(33));
}
function pl(e) {
	return e[Jn] || null;
}
var Ei = [],
	Xt = -1;
function xt(e) {
	return { current: e };
}
function V(e) {
	0 > Xt || ((e.current = Ei[Xt]), (Ei[Xt] = null), Xt--);
}
function W(e, t) {
	Xt++, (Ei[Xt] = e.current), (e.current = t);
}
var St = {},
	de = xt(St),
	we = xt(!1),
	Ot = St;
function an(e, t) {
	var n = e.type.contextTypes;
	if (!n) return St;
	var r = e.stateNode;
	if (r && r.__reactInternalMemoizedUnmaskedChildContext === t)
		return r.__reactInternalMemoizedMaskedChildContext;
	var l = {},
		i;
	for (i in n) l[i] = t[i];
	return (
		r &&
			((e = e.stateNode),
			(e.__reactInternalMemoizedUnmaskedChildContext = t),
			(e.__reactInternalMemoizedMaskedChildContext = l)),
		l
	);
}
function Se(e) {
	return (e = e.childContextTypes), e != null;
}
function Yr() {
	V(we), V(de);
}
function gs(e, t, n) {
	if (de.current !== St) throw Error(w(168));
	W(de, t), W(we, n);
}
function la(e, t, n) {
	var r = e.stateNode;
	if (((t = t.childContextTypes), typeof r.getChildContext != "function"))
		return n;
	r = r.getChildContext();
	for (var l in r) if (!(l in t)) throw Error(w(108, Wc(e) || "Unknown", l));
	return Y({}, n, r);
}
function Gr(e) {
	return (
		(e =
			((e = e.stateNode) && e.__reactInternalMemoizedMergedChildContext) || St),
		(Ot = de.current),
		W(de, e),
		W(we, we.current),
		!0
	);
}
function ws(e, t, n) {
	var r = e.stateNode;
	if (!r) throw Error(w(169));
	n
		? ((e = la(e, t, Ot)),
			(r.__reactInternalMemoizedMergedChildContext = e),
			V(we),
			V(de),
			W(de, e))
		: V(we),
		W(we, n);
}
var Xe = null,
	hl = !1,
	Wl = !1;
function ia(e) {
	Xe === null ? (Xe = [e]) : Xe.push(e);
}
function lf(e) {
	(hl = !0), ia(e);
}
function Nt() {
	if (!Wl && Xe !== null) {
		Wl = !0;
		var e = 0,
			t = A;
		try {
			var n = Xe;
			for (A = 1; e < n.length; e++) {
				var r = n[e];
				do r = r(!0);
				while (r !== null);
			}
			(Xe = null), (hl = !1);
		} catch (l) {
			throw (Xe !== null && (Xe = Xe.slice(e + 1)), Lu(to, Nt), l);
		} finally {
			(A = t), (Wl = !1);
		}
	}
	return null;
}
var Zt = [],
	Jt = 0,
	Xr = null,
	Zr = 0,
	Pe = [],
	Te = 0,
	Dt = null,
	Ze = 1,
	Je = "";
function _t(e, t) {
	(Zt[Jt++] = Zr), (Zt[Jt++] = Xr), (Xr = e), (Zr = t);
}
function oa(e, t, n) {
	(Pe[Te++] = Ze), (Pe[Te++] = Je), (Pe[Te++] = Dt), (Dt = e);
	var r = Ze;
	e = Je;
	var l = 32 - Ae(r) - 1;
	(r &= ~(1 << l)), (n += 1);
	var i = 32 - Ae(t) + l;
	if (30 < i) {
		var o = l - (l % 5);
		(i = (r & ((1 << o) - 1)).toString(32)),
			(r >>= o),
			(l -= o),
			(Ze = (1 << (32 - Ae(t) + l)) | (n << l) | r),
			(Je = i + e);
	} else (Ze = (1 << i) | (n << l) | r), (Je = e);
}
function co(e) {
	e.return !== null && (_t(e, 1), oa(e, 1, 0));
}
function fo(e) {
	for (; e === Xr; )
		(Xr = Zt[--Jt]), (Zt[Jt] = null), (Zr = Zt[--Jt]), (Zt[Jt] = null);
	for (; e === Dt; )
		(Dt = Pe[--Te]),
			(Pe[Te] = null),
			(Je = Pe[--Te]),
			(Pe[Te] = null),
			(Ze = Pe[--Te]),
			(Pe[Te] = null);
}
var Ee = null,
	Ne = null,
	H = !1,
	Me = null;
function sa(e, t) {
	var n = Le(5, null, null, 0);
	(n.elementType = "DELETED"),
		(n.stateNode = t),
		(n.return = e),
		(t = e.deletions),
		t === null ? ((e.deletions = [n]), (e.flags |= 16)) : t.push(n);
}
function Ss(e, t) {
	switch (e.tag) {
		case 5: {
			var n = e.type;
			return (
				(t =
					t.nodeType !== 1 || n.toLowerCase() !== t.nodeName.toLowerCase()
						? null
						: t),
				t !== null
					? ((e.stateNode = t), (Ee = e), (Ne = ht(t.firstChild)), !0)
					: !1
			);
		}
		case 6:
			return (
				(t = e.pendingProps === "" || t.nodeType !== 3 ? null : t),
				t !== null ? ((e.stateNode = t), (Ee = e), (Ne = null), !0) : !1
			);
		case 13:
			return (
				(t = t.nodeType !== 8 ? null : t),
				t !== null
					? ((n = Dt !== null ? { id: Ze, overflow: Je } : null),
						(e.memoizedState = {
							dehydrated: t,
							treeContext: n,
							retryLane: 1073741824,
						}),
						(n = Le(18, null, null, 0)),
						(n.stateNode = t),
						(n.return = e),
						(e.child = n),
						(Ee = e),
						(Ne = null),
						!0)
					: !1
			);
		default:
			return !1;
	}
}
function Ci(e) {
	return (e.mode & 1) !== 0 && (e.flags & 128) === 0;
}
function _i(e) {
	if (H) {
		var t = Ne;
		if (t) {
			var n = t;
			if (!Ss(e, t)) {
				if (Ci(e)) throw Error(w(418));
				t = ht(n.nextSibling);
				var r = Ee;
				t && Ss(e, t)
					? sa(r, n)
					: ((e.flags = (e.flags & -4097) | 2), (H = !1), (Ee = e));
			}
		} else {
			if (Ci(e)) throw Error(w(418));
			(e.flags = (e.flags & -4097) | 2), (H = !1), (Ee = e);
		}
	}
}
function ks(e) {
	for (e = e.return; e !== null && e.tag !== 5 && e.tag !== 3 && e.tag !== 13; )
		e = e.return;
	Ee = e;
}
function Sr(e) {
	if (e !== Ee) return !1;
	if (!H) return ks(e), (H = !0), !1;
	var t;
	if (
		((t = e.tag !== 3) &&
			!(t = e.tag !== 5) &&
			((t = e.type),
			(t = t !== "head" && t !== "body" && !ki(e.type, e.memoizedProps))),
		t && (t = Ne))
	) {
		if (Ci(e)) throw (ua(), Error(w(418)));
		for (; t; ) sa(e, t), (t = ht(t.nextSibling));
	}
	if ((ks(e), e.tag === 13)) {
		if (((e = e.memoizedState), (e = e !== null ? e.dehydrated : null), !e))
			throw Error(w(317));
		e: {
			for (e = e.nextSibling, t = 0; e; ) {
				if (e.nodeType === 8) {
					var n = e.data;
					if (n === "/$") {
						if (t === 0) {
							Ne = ht(e.nextSibling);
							break e;
						}
						t--;
					} else (n !== "$" && n !== "$!" && n !== "$?") || t++;
				}
				e = e.nextSibling;
			}
			Ne = null;
		}
	} else Ne = Ee ? ht(e.stateNode.nextSibling) : null;
	return !0;
}
function ua() {
	for (var e = Ne; e; ) e = ht(e.nextSibling);
}
function cn() {
	(Ne = Ee = null), (H = !1);
}
function po(e) {
	Me === null ? (Me = [e]) : Me.push(e);
}
var of = rt.ReactCurrentBatchConfig;
function Cn(e, t, n) {
	if (
		((e = n.ref), e !== null && typeof e != "function" && typeof e != "object")
	) {
		if (n._owner) {
			if (((n = n._owner), n)) {
				if (n.tag !== 1) throw Error(w(309));
				var r = n.stateNode;
			}
			if (!r) throw Error(w(147, e));
			var l = r,
				i = "" + e;
			return t !== null &&
				t.ref !== null &&
				typeof t.ref == "function" &&
				t.ref._stringRef === i
				? t.ref
				: ((t = (o) => {
						var s = l.refs;
						o === null ? delete s[i] : (s[i] = o);
					}),
					(t._stringRef = i),
					t);
		}
		if (typeof e != "string") throw Error(w(284));
		if (!n._owner) throw Error(w(290, e));
	}
	return e;
}
function kr(e, t) {
	throw (
		((e = Object.prototype.toString.call(t)),
		Error(
			w(
				31,
				e === "[object Object]"
					? "object with keys {" + Object.keys(t).join(", ") + "}"
					: e,
			),
		))
	);
}
function xs(e) {
	var t = e._init;
	return t(e._payload);
}
function aa(e) {
	function t(p, a) {
		if (e) {
			var d = p.deletions;
			d === null ? ((p.deletions = [a]), (p.flags |= 16)) : d.push(a);
		}
	}
	function n(p, a) {
		if (!e) return null;
		for (; a !== null; ) t(p, a), (a = a.sibling);
		return null;
	}
	function r(p, a) {
		for (p = new Map(); a !== null; )
			a.key !== null ? p.set(a.key, a) : p.set(a.index, a), (a = a.sibling);
		return p;
	}
	function l(p, a) {
		return (p = gt(p, a)), (p.index = 0), (p.sibling = null), p;
	}
	function i(p, a, d) {
		return (
			(p.index = d),
			e
				? ((d = p.alternate),
					d !== null
						? ((d = d.index), d < a ? ((p.flags |= 2), a) : d)
						: ((p.flags |= 2), a))
				: ((p.flags |= 1048576), a)
		);
	}
	function o(p) {
		return e && p.alternate === null && (p.flags |= 2), p;
	}
	function s(p, a, d, y) {
		return a === null || a.tag !== 6
			? ((a = Gl(d, p.mode, y)), (a.return = p), a)
			: ((a = l(a, d)), (a.return = p), a);
	}
	function u(p, a, d, y) {
		var N = d.type;
		return N === Ht
			? v(p, a, d.props.children, y, d.key)
			: a !== null &&
					(a.elementType === N ||
						(typeof N == "object" &&
							N !== null &&
							N.$$typeof === it &&
							xs(N) === a.type))
				? ((y = l(a, d.props)), (y.ref = Cn(p, a, d)), (y.return = p), y)
				: ((y = Mr(d.type, d.key, d.props, null, p.mode, y)),
					(y.ref = Cn(p, a, d)),
					(y.return = p),
					y);
	}
	function f(p, a, d, y) {
		return a === null ||
			a.tag !== 4 ||
			a.stateNode.containerInfo !== d.containerInfo ||
			a.stateNode.implementation !== d.implementation
			? ((a = Xl(d, p.mode, y)), (a.return = p), a)
			: ((a = l(a, d.children || [])), (a.return = p), a);
	}
	function v(p, a, d, y, N) {
		return a === null || a.tag !== 7
			? ((a = Rt(d, p.mode, y, N)), (a.return = p), a)
			: ((a = l(a, d)), (a.return = p), a);
	}
	function h(p, a, d) {
		if ((typeof a == "string" && a !== "") || typeof a == "number")
			return (a = Gl("" + a, p.mode, d)), (a.return = p), a;
		if (typeof a == "object" && a !== null) {
			switch (a.$$typeof) {
				case cr:
					return (
						(d = Mr(a.type, a.key, a.props, null, p.mode, d)),
						(d.ref = Cn(p, null, a)),
						(d.return = p),
						d
					);
				case Vt:
					return (a = Xl(a, p.mode, d)), (a.return = p), a;
				case it: {
					var y = a._init;
					return h(p, y(a._payload), d);
				}
			}
			if (Tn(a) || Sn(a))
				return (a = Rt(a, p.mode, d, null)), (a.return = p), a;
			kr(p, a);
		}
		return null;
	}
	function m(p, a, d, y) {
		var N = a !== null ? a.key : null;
		if ((typeof d == "string" && d !== "") || typeof d == "number")
			return N !== null ? null : s(p, a, "" + d, y);
		if (typeof d == "object" && d !== null) {
			switch (d.$$typeof) {
				case cr:
					return d.key === N ? u(p, a, d, y) : null;
				case Vt:
					return d.key === N ? f(p, a, d, y) : null;
				case it:
					return (N = d._init), m(p, a, N(d._payload), y);
			}
			if (Tn(d) || Sn(d)) return N !== null ? null : v(p, a, d, y, null);
			kr(p, d);
		}
		return null;
	}
	function g(p, a, d, y, N) {
		if ((typeof y == "string" && y !== "") || typeof y == "number")
			return (p = p.get(d) || null), s(a, p, "" + y, N);
		if (typeof y == "object" && y !== null) {
			switch (y.$$typeof) {
				case cr:
					return (p = p.get(y.key === null ? d : y.key) || null), u(a, p, y, N);
				case Vt:
					return (p = p.get(y.key === null ? d : y.key) || null), f(a, p, y, N);
				case it: {
					var k = y._init;
					return g(p, a, d, k(y._payload), N);
				}
			}
			if (Tn(y) || Sn(y)) return (p = p.get(d) || null), v(a, p, y, N, null);
			kr(a, y);
		}
		return null;
	}
	function x(p, a, d, y) {
		for (
			var N = null, k = null, C = a, L = (a = 0), j = null;
			C !== null && L < d.length;
			L++
		) {
			C.index > L ? ((j = C), (C = null)) : (j = C.sibling);
			var P = m(p, C, d[L], y);
			if (P === null) {
				C === null && (C = j);
				break;
			}
			e && C && P.alternate === null && t(p, C),
				(a = i(P, a, L)),
				k === null ? (N = P) : (k.sibling = P),
				(k = P),
				(C = j);
		}
		if (L === d.length) return n(p, C), H && _t(p, L), N;
		if (C === null) {
			for (; L < d.length; L++)
				(C = h(p, d[L], y)),
					C !== null &&
						((a = i(C, a, L)), k === null ? (N = C) : (k.sibling = C), (k = C));
			return H && _t(p, L), N;
		}
		for (C = r(p, C); L < d.length; L++)
			(j = g(C, p, L, d[L], y)),
				j !== null &&
					(e && j.alternate !== null && C.delete(j.key === null ? L : j.key),
					(a = i(j, a, L)),
					k === null ? (N = j) : (k.sibling = j),
					(k = j));
		return e && C.forEach((U) => t(p, U)), H && _t(p, L), N;
	}
	function E(p, a, d, y) {
		var N = Sn(d);
		if (typeof N != "function") throw Error(w(150));
		if (((d = N.call(d)), d == null)) throw Error(w(151));
		for (
			var k = (N = null), C = a, L = (a = 0), j = null, P = d.next();
			C !== null && !P.done;
			L++, P = d.next()
		) {
			C.index > L ? ((j = C), (C = null)) : (j = C.sibling);
			var U = m(p, C, P.value, y);
			if (U === null) {
				C === null && (C = j);
				break;
			}
			e && C && U.alternate === null && t(p, C),
				(a = i(U, a, L)),
				k === null ? (N = U) : (k.sibling = U),
				(k = U),
				(C = j);
		}
		if (P.done) return n(p, C), H && _t(p, L), N;
		if (C === null) {
			for (; !P.done; L++, P = d.next())
				(P = h(p, P.value, y)),
					P !== null &&
						((a = i(P, a, L)), k === null ? (N = P) : (k.sibling = P), (k = P));
			return H && _t(p, L), N;
		}
		for (C = r(p, C); !P.done; L++, P = d.next())
			(P = g(C, p, L, P.value, y)),
				P !== null &&
					(e && P.alternate !== null && C.delete(P.key === null ? L : P.key),
					(a = i(P, a, L)),
					k === null ? (N = P) : (k.sibling = P),
					(k = P));
		return e && C.forEach((fe) => t(p, fe)), H && _t(p, L), N;
	}
	function D(p, a, d, y) {
		if (
			(typeof d == "object" &&
				d !== null &&
				d.type === Ht &&
				d.key === null &&
				(d = d.props.children),
			typeof d == "object" && d !== null)
		) {
			switch (d.$$typeof) {
				case cr:
					e: {
						for (var N = d.key, k = a; k !== null; ) {
							if (k.key === N) {
								if (((N = d.type), N === Ht)) {
									if (k.tag === 7) {
										n(p, k.sibling),
											(a = l(k, d.props.children)),
											(a.return = p),
											(p = a);
										break e;
									}
								} else if (
									k.elementType === N ||
									(typeof N == "object" &&
										N !== null &&
										N.$$typeof === it &&
										xs(N) === k.type)
								) {
									n(p, k.sibling),
										(a = l(k, d.props)),
										(a.ref = Cn(p, k, d)),
										(a.return = p),
										(p = a);
									break e;
								}
								n(p, k);
								break;
							} else t(p, k);
							k = k.sibling;
						}
						d.type === Ht
							? ((a = Rt(d.props.children, p.mode, y, d.key)),
								(a.return = p),
								(p = a))
							: ((y = Mr(d.type, d.key, d.props, null, p.mode, y)),
								(y.ref = Cn(p, a, d)),
								(y.return = p),
								(p = y));
					}
					return o(p);
				case Vt:
					e: {
						for (k = d.key; a !== null; ) {
							if (a.key === k)
								if (
									a.tag === 4 &&
									a.stateNode.containerInfo === d.containerInfo &&
									a.stateNode.implementation === d.implementation
								) {
									n(p, a.sibling),
										(a = l(a, d.children || [])),
										(a.return = p),
										(p = a);
									break e;
								} else {
									n(p, a);
									break;
								}
							else t(p, a);
							a = a.sibling;
						}
						(a = Xl(d, p.mode, y)), (a.return = p), (p = a);
					}
					return o(p);
				case it:
					return (k = d._init), D(p, a, k(d._payload), y);
			}
			if (Tn(d)) return x(p, a, d, y);
			if (Sn(d)) return E(p, a, d, y);
			kr(p, d);
		}
		return (typeof d == "string" && d !== "") || typeof d == "number"
			? ((d = "" + d),
				a !== null && a.tag === 6
					? (n(p, a.sibling), (a = l(a, d)), (a.return = p), (p = a))
					: (n(p, a), (a = Gl(d, p.mode, y)), (a.return = p), (p = a)),
				o(p))
			: n(p, a);
	}
	return D;
}
var dn = aa(!0),
	ca = aa(!1),
	Jr = xt(null),
	qr = null,
	qt = null,
	ho = null;
function mo() {
	ho = qt = qr = null;
}
function vo(e) {
	var t = Jr.current;
	V(Jr), (e._currentValue = t);
}
function ji(e, t, n) {
	for (; e !== null; ) {
		var r = e.alternate;
		if (
			((e.childLanes & t) !== t
				? ((e.childLanes |= t), r !== null && (r.childLanes |= t))
				: r !== null && (r.childLanes & t) !== t && (r.childLanes |= t),
			e === n)
		)
			break;
		e = e.return;
	}
}
function on(e, t) {
	(qr = e),
		(ho = qt = null),
		(e = e.dependencies),
		e !== null &&
			e.firstContext !== null &&
			(e.lanes & t && (ge = !0), (e.firstContext = null));
}
function Re(e) {
	var t = e._currentValue;
	if (ho !== e)
		if (((e = { context: e, memoizedValue: t, next: null }), qt === null)) {
			if (qr === null) throw Error(w(308));
			(qt = e), (qr.dependencies = { lanes: 0, firstContext: e });
		} else qt = qt.next = e;
	return t;
}
var Tt = null;
function yo(e) {
	Tt === null ? (Tt = [e]) : Tt.push(e);
}
function da(e, t, n, r) {
	var l = t.interleaved;
	return (
		l === null ? ((n.next = n), yo(t)) : ((n.next = l.next), (l.next = n)),
		(t.interleaved = n),
		tt(e, r)
	);
}
function tt(e, t) {
	e.lanes |= t;
	var n = e.alternate;
	for (n !== null && (n.lanes |= t), n = e, e = e.return; e !== null; )
		(e.childLanes |= t),
			(n = e.alternate),
			n !== null && (n.childLanes |= t),
			(n = e),
			(e = e.return);
	return n.tag === 3 ? n.stateNode : null;
}
var ot = !1;
function go(e) {
	e.updateQueue = {
		baseState: e.memoizedState,
		firstBaseUpdate: null,
		lastBaseUpdate: null,
		shared: { pending: null, interleaved: null, lanes: 0 },
		effects: null,
	};
}
function fa(e, t) {
	(e = e.updateQueue),
		t.updateQueue === e &&
			(t.updateQueue = {
				baseState: e.baseState,
				firstBaseUpdate: e.firstBaseUpdate,
				lastBaseUpdate: e.lastBaseUpdate,
				shared: e.shared,
				effects: e.effects,
			});
}
function qe(e, t) {
	return {
		eventTime: e,
		lane: t,
		tag: 0,
		payload: null,
		callback: null,
		next: null,
	};
}
function mt(e, t, n) {
	var r = e.updateQueue;
	if (r === null) return null;
	if (((r = r.shared), M & 2)) {
		var l = r.pending;
		return (
			l === null ? (t.next = t) : ((t.next = l.next), (l.next = t)),
			(r.pending = t),
			tt(e, n)
		);
	}
	return (
		(l = r.interleaved),
		l === null ? ((t.next = t), yo(r)) : ((t.next = l.next), (l.next = t)),
		(r.interleaved = t),
		tt(e, n)
	);
}
function zr(e, t, n) {
	if (
		((t = t.updateQueue), t !== null && ((t = t.shared), (n & 4194240) !== 0))
	) {
		var r = t.lanes;
		(r &= e.pendingLanes), (n |= r), (t.lanes = n), no(e, n);
	}
}
function Ns(e, t) {
	var n = e.updateQueue,
		r = e.alternate;
	if (r !== null && ((r = r.updateQueue), n === r)) {
		var l = null,
			i = null;
		if (((n = n.firstBaseUpdate), n !== null)) {
			do {
				var o = {
					eventTime: n.eventTime,
					lane: n.lane,
					tag: n.tag,
					payload: n.payload,
					callback: n.callback,
					next: null,
				};
				i === null ? (l = i = o) : (i = i.next = o), (n = n.next);
			} while (n !== null);
			i === null ? (l = i = t) : (i = i.next = t);
		} else l = i = t;
		(n = {
			baseState: r.baseState,
			firstBaseUpdate: l,
			lastBaseUpdate: i,
			shared: r.shared,
			effects: r.effects,
		}),
			(e.updateQueue = n);
		return;
	}
	(e = n.lastBaseUpdate),
		e === null ? (n.firstBaseUpdate = t) : (e.next = t),
		(n.lastBaseUpdate = t);
}
function br(e, t, n, r) {
	var l = e.updateQueue;
	ot = !1;
	var i = l.firstBaseUpdate,
		o = l.lastBaseUpdate,
		s = l.shared.pending;
	if (s !== null) {
		l.shared.pending = null;
		var u = s,
			f = u.next;
		(u.next = null), o === null ? (i = f) : (o.next = f), (o = u);
		var v = e.alternate;
		v !== null &&
			((v = v.updateQueue),
			(s = v.lastBaseUpdate),
			s !== o &&
				(s === null ? (v.firstBaseUpdate = f) : (s.next = f),
				(v.lastBaseUpdate = u)));
	}
	if (i !== null) {
		var h = l.baseState;
		(o = 0), (v = f = u = null), (s = i);
		do {
			var m = s.lane,
				g = s.eventTime;
			if ((r & m) === m) {
				v !== null &&
					(v = v.next =
						{
							eventTime: g,
							lane: 0,
							tag: s.tag,
							payload: s.payload,
							callback: s.callback,
							next: null,
						});
				e: {
					var x = e,
						E = s;
					switch (((m = t), (g = n), E.tag)) {
						case 1:
							if (((x = E.payload), typeof x == "function")) {
								h = x.call(g, h, m);
								break e;
							}
							h = x;
							break e;
						case 3:
							x.flags = (x.flags & -65537) | 128;
						case 0:
							if (
								((x = E.payload),
								(m = typeof x == "function" ? x.call(g, h, m) : x),
								m == null)
							)
								break e;
							h = Y({}, h, m);
							break e;
						case 2:
							ot = !0;
					}
				}
				s.callback !== null &&
					s.lane !== 0 &&
					((e.flags |= 64),
					(m = l.effects),
					m === null ? (l.effects = [s]) : m.push(s));
			} else
				(g = {
					eventTime: g,
					lane: m,
					tag: s.tag,
					payload: s.payload,
					callback: s.callback,
					next: null,
				}),
					v === null ? ((f = v = g), (u = h)) : (v = v.next = g),
					(o |= m);
			if (((s = s.next), s === null)) {
				if (((s = l.shared.pending), s === null)) break;
				(m = s),
					(s = m.next),
					(m.next = null),
					(l.lastBaseUpdate = m),
					(l.shared.pending = null);
			}
		} while (1);
		if (
			(v === null && (u = h),
			(l.baseState = u),
			(l.firstBaseUpdate = f),
			(l.lastBaseUpdate = v),
			(t = l.shared.interleaved),
			t !== null)
		) {
			l = t;
			do (o |= l.lane), (l = l.next);
			while (l !== t);
		} else i === null && (l.shared.lanes = 0);
		(Ft |= o), (e.lanes = o), (e.memoizedState = h);
	}
}
function Es(e, t, n) {
	if (((e = t.effects), (t.effects = null), e !== null))
		for (t = 0; t < e.length; t++) {
			var r = e[t],
				l = r.callback;
			if (l !== null) {
				if (((r.callback = null), (r = n), typeof l != "function"))
					throw Error(w(191, l));
				l.call(r);
			}
		}
}
var ur = {},
	Qe = xt(ur),
	qn = xt(ur),
	bn = xt(ur);
function Lt(e) {
	if (e === ur) throw Error(w(174));
	return e;
}
function wo(e, t) {
	switch ((W(bn, t), W(qn, e), W(Qe, ur), (e = t.nodeType), e)) {
		case 9:
		case 11:
			t = (t = t.documentElement) ? t.namespaceURI : si(null, "");
			break;
		default:
			(e = e === 8 ? t.parentNode : t),
				(t = e.namespaceURI || null),
				(e = e.tagName),
				(t = si(t, e));
	}
	V(Qe), W(Qe, t);
}
function fn() {
	V(Qe), V(qn), V(bn);
}
function pa(e) {
	Lt(bn.current);
	var t = Lt(Qe.current),
		n = si(t, e.type);
	t !== n && (W(qn, e), W(Qe, n));
}
function So(e) {
	qn.current === e && (V(Qe), V(qn));
}
var K = xt(0);
function el(e) {
	for (var t = e; t !== null; ) {
		if (t.tag === 13) {
			var n = t.memoizedState;
			if (
				n !== null &&
				((n = n.dehydrated), n === null || n.data === "$?" || n.data === "$!")
			)
				return t;
		} else if (t.tag === 19 && t.memoizedProps.revealOrder !== void 0) {
			if (t.flags & 128) return t;
		} else if (t.child !== null) {
			(t.child.return = t), (t = t.child);
			continue;
		}
		if (t === e) break;
		for (; t.sibling === null; ) {
			if (t.return === null || t.return === e) return null;
			t = t.return;
		}
		(t.sibling.return = t.return), (t = t.sibling);
	}
	return null;
}
var Bl = [];
function ko() {
	for (var e = 0; e < Bl.length; e++)
		Bl[e]._workInProgressVersionPrimary = null;
	Bl.length = 0;
}
var Rr = rt.ReactCurrentDispatcher,
	Vl = rt.ReactCurrentBatchConfig,
	It = 0,
	Q = null,
	ee = null,
	ne = null,
	tl = !1,
	Mn = !1,
	er = 0,
	sf = 0;
function ue() {
	throw Error(w(321));
}
function xo(e, t) {
	if (t === null) return !1;
	for (var n = 0; n < t.length && n < e.length; n++)
		if (!$e(e[n], t[n])) return !1;
	return !0;
}
function No(e, t, n, r, l, i) {
	if (
		((It = i),
		(Q = t),
		(t.memoizedState = null),
		(t.updateQueue = null),
		(t.lanes = 0),
		(Rr.current = e === null || e.memoizedState === null ? df : ff),
		(e = n(r, l)),
		Mn)
	) {
		i = 0;
		do {
			if (((Mn = !1), (er = 0), 25 <= i)) throw Error(w(301));
			(i += 1),
				(ne = ee = null),
				(t.updateQueue = null),
				(Rr.current = pf),
				(e = n(r, l));
		} while (Mn);
	}
	if (
		((Rr.current = nl),
		(t = ee !== null && ee.next !== null),
		(It = 0),
		(ne = ee = Q = null),
		(tl = !1),
		t)
	)
		throw Error(w(300));
	return e;
}
function Eo() {
	var e = er !== 0;
	return (er = 0), e;
}
function Ve() {
	var e = {
		memoizedState: null,
		baseState: null,
		baseQueue: null,
		queue: null,
		next: null,
	};
	return ne === null ? (Q.memoizedState = ne = e) : (ne = ne.next = e), ne;
}
function Oe() {
	if (ee === null) {
		var e = Q.alternate;
		e = e !== null ? e.memoizedState : null;
	} else e = ee.next;
	var t = ne === null ? Q.memoizedState : ne.next;
	if (t !== null) (ne = t), (ee = e);
	else {
		if (e === null) throw Error(w(310));
		(ee = e),
			(e = {
				memoizedState: ee.memoizedState,
				baseState: ee.baseState,
				baseQueue: ee.baseQueue,
				queue: ee.queue,
				next: null,
			}),
			ne === null ? (Q.memoizedState = ne = e) : (ne = ne.next = e);
	}
	return ne;
}
function tr(e, t) {
	return typeof t == "function" ? t(e) : t;
}
function Hl(e) {
	var t = Oe(),
		n = t.queue;
	if (n === null) throw Error(w(311));
	n.lastRenderedReducer = e;
	var r = ee,
		l = r.baseQueue,
		i = n.pending;
	if (i !== null) {
		if (l !== null) {
			var o = l.next;
			(l.next = i.next), (i.next = o);
		}
		(r.baseQueue = l = i), (n.pending = null);
	}
	if (l !== null) {
		(i = l.next), (r = r.baseState);
		var s = (o = null),
			u = null,
			f = i;
		do {
			var v = f.lane;
			if ((It & v) === v)
				u !== null &&
					(u = u.next =
						{
							lane: 0,
							action: f.action,
							hasEagerState: f.hasEagerState,
							eagerState: f.eagerState,
							next: null,
						}),
					(r = f.hasEagerState ? f.eagerState : e(r, f.action));
			else {
				var h = {
					lane: v,
					action: f.action,
					hasEagerState: f.hasEagerState,
					eagerState: f.eagerState,
					next: null,
				};
				u === null ? ((s = u = h), (o = r)) : (u = u.next = h),
					(Q.lanes |= v),
					(Ft |= v);
			}
			f = f.next;
		} while (f !== null && f !== i);
		u === null ? (o = r) : (u.next = s),
			$e(r, t.memoizedState) || (ge = !0),
			(t.memoizedState = r),
			(t.baseState = o),
			(t.baseQueue = u),
			(n.lastRenderedState = r);
	}
	if (((e = n.interleaved), e !== null)) {
		l = e;
		do (i = l.lane), (Q.lanes |= i), (Ft |= i), (l = l.next);
		while (l !== e);
	} else l === null && (n.lanes = 0);
	return [t.memoizedState, n.dispatch];
}
function Kl(e) {
	var t = Oe(),
		n = t.queue;
	if (n === null) throw Error(w(311));
	n.lastRenderedReducer = e;
	var r = n.dispatch,
		l = n.pending,
		i = t.memoizedState;
	if (l !== null) {
		n.pending = null;
		var o = (l = l.next);
		do (i = e(i, o.action)), (o = o.next);
		while (o !== l);
		$e(i, t.memoizedState) || (ge = !0),
			(t.memoizedState = i),
			t.baseQueue === null && (t.baseState = i),
			(n.lastRenderedState = i);
	}
	return [i, r];
}
function ha() {}
function ma(e, t) {
	var n = Q,
		r = Oe(),
		l = t(),
		i = !$e(r.memoizedState, l);
	if (
		(i && ((r.memoizedState = l), (ge = !0)),
		(r = r.queue),
		Co(ga.bind(null, n, r, e), [e]),
		r.getSnapshot !== t || i || (ne !== null && ne.memoizedState.tag & 1))
	) {
		if (
			((n.flags |= 2048),
			nr(9, ya.bind(null, n, r, l, t), void 0, null),
			re === null)
		)
			throw Error(w(349));
		It & 30 || va(n, t, l);
	}
	return l;
}
function va(e, t, n) {
	(e.flags |= 16384),
		(e = { getSnapshot: t, value: n }),
		(t = Q.updateQueue),
		t === null
			? ((t = { lastEffect: null, stores: null }),
				(Q.updateQueue = t),
				(t.stores = [e]))
			: ((n = t.stores), n === null ? (t.stores = [e]) : n.push(e));
}
function ya(e, t, n, r) {
	(t.value = n), (t.getSnapshot = r), wa(t) && Sa(e);
}
function ga(e, t, n) {
	return n(() => {
		wa(t) && Sa(e);
	});
}
function wa(e) {
	var t = e.getSnapshot;
	e = e.value;
	try {
		var n = t();
		return !$e(e, n);
	} catch {
		return !0;
	}
}
function Sa(e) {
	var t = tt(e, 1);
	t !== null && Ue(t, e, 1, -1);
}
function Cs(e) {
	var t = Ve();
	return (
		typeof e == "function" && (e = e()),
		(t.memoizedState = t.baseState = e),
		(e = {
			pending: null,
			interleaved: null,
			lanes: 0,
			dispatch: null,
			lastRenderedReducer: tr,
			lastRenderedState: e,
		}),
		(t.queue = e),
		(e = e.dispatch = cf.bind(null, Q, e)),
		[t.memoizedState, e]
	);
}
function nr(e, t, n, r) {
	return (
		(e = { tag: e, create: t, destroy: n, deps: r, next: null }),
		(t = Q.updateQueue),
		t === null
			? ((t = { lastEffect: null, stores: null }),
				(Q.updateQueue = t),
				(t.lastEffect = e.next = e))
			: ((n = t.lastEffect),
				n === null
					? (t.lastEffect = e.next = e)
					: ((r = n.next), (n.next = e), (e.next = r), (t.lastEffect = e))),
		e
	);
}
function ka() {
	return Oe().memoizedState;
}
function Or(e, t, n, r) {
	var l = Ve();
	(Q.flags |= e),
		(l.memoizedState = nr(1 | t, n, void 0, r === void 0 ? null : r));
}
function ml(e, t, n, r) {
	var l = Oe();
	r = r === void 0 ? null : r;
	var i = void 0;
	if (ee !== null) {
		var o = ee.memoizedState;
		if (((i = o.destroy), r !== null && xo(r, o.deps))) {
			l.memoizedState = nr(t, n, i, r);
			return;
		}
	}
	(Q.flags |= e), (l.memoizedState = nr(1 | t, n, i, r));
}
function _s(e, t) {
	return Or(8390656, 8, e, t);
}
function Co(e, t) {
	return ml(2048, 8, e, t);
}
function xa(e, t) {
	return ml(4, 2, e, t);
}
function Na(e, t) {
	return ml(4, 4, e, t);
}
function Ea(e, t) {
	if (typeof t == "function")
		return (
			(e = e()),
			t(e),
			() => {
				t(null);
			}
		);
	if (t != null)
		return (
			(e = e()),
			(t.current = e),
			() => {
				t.current = null;
			}
		);
}
function Ca(e, t, n) {
	return (
		(n = n != null ? n.concat([e]) : null), ml(4, 4, Ea.bind(null, t, e), n)
	);
}
function _o() {}
function _a(e, t) {
	var n = Oe();
	t = t === void 0 ? null : t;
	var r = n.memoizedState;
	return r !== null && t !== null && xo(t, r[1])
		? r[0]
		: ((n.memoizedState = [e, t]), e);
}
function ja(e, t) {
	var n = Oe();
	t = t === void 0 ? null : t;
	var r = n.memoizedState;
	return r !== null && t !== null && xo(t, r[1])
		? r[0]
		: ((e = e()), (n.memoizedState = [e, t]), e);
}
function Pa(e, t, n) {
	return It & 21
		? ($e(n, t) || ((n = Ou()), (Q.lanes |= n), (Ft |= n), (e.baseState = !0)),
			t)
		: (e.baseState && ((e.baseState = !1), (ge = !0)), (e.memoizedState = n));
}
function uf(e, t) {
	var n = A;
	(A = n !== 0 && 4 > n ? n : 4), e(!0);
	var r = Vl.transition;
	Vl.transition = {};
	try {
		e(!1), t();
	} finally {
		(A = n), (Vl.transition = r);
	}
}
function Ta() {
	return Oe().memoizedState;
}
function af(e, t, n) {
	var r = yt(e);
	if (
		((n = {
			lane: r,
			action: n,
			hasEagerState: !1,
			eagerState: null,
			next: null,
		}),
		La(e))
	)
		za(t, n);
	else if (((n = da(e, t, n, r)), n !== null)) {
		var l = he();
		Ue(n, e, r, l), Ra(n, t, r);
	}
}
function cf(e, t, n) {
	var r = yt(e),
		l = { lane: r, action: n, hasEagerState: !1, eagerState: null, next: null };
	if (La(e)) za(t, l);
	else {
		var i = e.alternate;
		if (
			e.lanes === 0 &&
			(i === null || i.lanes === 0) &&
			((i = t.lastRenderedReducer), i !== null)
		)
			try {
				var o = t.lastRenderedState,
					s = i(o, n);
				if (((l.hasEagerState = !0), (l.eagerState = s), $e(s, o))) {
					var u = t.interleaved;
					u === null
						? ((l.next = l), yo(t))
						: ((l.next = u.next), (u.next = l)),
						(t.interleaved = l);
					return;
				}
			} catch {
			} finally {
			}
		(n = da(e, t, l, r)),
			n !== null && ((l = he()), Ue(n, e, r, l), Ra(n, t, r));
	}
}
function La(e) {
	var t = e.alternate;
	return e === Q || (t !== null && t === Q);
}
function za(e, t) {
	Mn = tl = !0;
	var n = e.pending;
	n === null ? (t.next = t) : ((t.next = n.next), (n.next = t)),
		(e.pending = t);
}
function Ra(e, t, n) {
	if (n & 4194240) {
		var r = t.lanes;
		(r &= e.pendingLanes), (n |= r), (t.lanes = n), no(e, n);
	}
}
var nl = {
		readContext: Re,
		useCallback: ue,
		useContext: ue,
		useEffect: ue,
		useImperativeHandle: ue,
		useInsertionEffect: ue,
		useLayoutEffect: ue,
		useMemo: ue,
		useReducer: ue,
		useRef: ue,
		useState: ue,
		useDebugValue: ue,
		useDeferredValue: ue,
		useTransition: ue,
		useMutableSource: ue,
		useSyncExternalStore: ue,
		useId: ue,
		unstable_isNewReconciler: !1,
	},
	df = {
		readContext: Re,
		useCallback: (e, t) => (
			(Ve().memoizedState = [e, t === void 0 ? null : t]), e
		),
		useContext: Re,
		useEffect: _s,
		useImperativeHandle: (e, t, n) => (
			(n = n != null ? n.concat([e]) : null),
			Or(4194308, 4, Ea.bind(null, t, e), n)
		),
		useLayoutEffect: (e, t) => Or(4194308, 4, e, t),
		useInsertionEffect: (e, t) => Or(4, 2, e, t),
		useMemo: (e, t) => {
			var n = Ve();
			return (
				(t = t === void 0 ? null : t), (e = e()), (n.memoizedState = [e, t]), e
			);
		},
		useReducer: (e, t, n) => {
			var r = Ve();
			return (
				(t = n !== void 0 ? n(t) : t),
				(r.memoizedState = r.baseState = t),
				(e = {
					pending: null,
					interleaved: null,
					lanes: 0,
					dispatch: null,
					lastRenderedReducer: e,
					lastRenderedState: t,
				}),
				(r.queue = e),
				(e = e.dispatch = af.bind(null, Q, e)),
				[r.memoizedState, e]
			);
		},
		useRef: (e) => {
			var t = Ve();
			return (e = { current: e }), (t.memoizedState = e);
		},
		useState: Cs,
		useDebugValue: _o,
		useDeferredValue: (e) => (Ve().memoizedState = e),
		useTransition: () => {
			var e = Cs(!1),
				t = e[0];
			return (e = uf.bind(null, e[1])), (Ve().memoizedState = e), [t, e];
		},
		useMutableSource: () => {},
		useSyncExternalStore: (e, t, n) => {
			var r = Q,
				l = Ve();
			if (H) {
				if (n === void 0) throw Error(w(407));
				n = n();
			} else {
				if (((n = t()), re === null)) throw Error(w(349));
				It & 30 || va(r, t, n);
			}
			l.memoizedState = n;
			var i = { value: n, getSnapshot: t };
			return (
				(l.queue = i),
				_s(ga.bind(null, r, i, e), [e]),
				(r.flags |= 2048),
				nr(9, ya.bind(null, r, i, n, t), void 0, null),
				n
			);
		},
		useId: () => {
			var e = Ve(),
				t = re.identifierPrefix;
			if (H) {
				var n = Je,
					r = Ze;
				(n = (r & ~(1 << (32 - Ae(r) - 1))).toString(32) + n),
					(t = ":" + t + "R" + n),
					(n = er++),
					0 < n && (t += "H" + n.toString(32)),
					(t += ":");
			} else (n = sf++), (t = ":" + t + "r" + n.toString(32) + ":");
			return (e.memoizedState = t);
		},
		unstable_isNewReconciler: !1,
	},
	ff = {
		readContext: Re,
		useCallback: _a,
		useContext: Re,
		useEffect: Co,
		useImperativeHandle: Ca,
		useInsertionEffect: xa,
		useLayoutEffect: Na,
		useMemo: ja,
		useReducer: Hl,
		useRef: ka,
		useState: () => Hl(tr),
		useDebugValue: _o,
		useDeferredValue: (e) => {
			var t = Oe();
			return Pa(t, ee.memoizedState, e);
		},
		useTransition: () => {
			var e = Hl(tr)[0],
				t = Oe().memoizedState;
			return [e, t];
		},
		useMutableSource: ha,
		useSyncExternalStore: ma,
		useId: Ta,
		unstable_isNewReconciler: !1,
	},
	pf = {
		readContext: Re,
		useCallback: _a,
		useContext: Re,
		useEffect: Co,
		useImperativeHandle: Ca,
		useInsertionEffect: xa,
		useLayoutEffect: Na,
		useMemo: ja,
		useReducer: Kl,
		useRef: ka,
		useState: () => Kl(tr),
		useDebugValue: _o,
		useDeferredValue: (e) => {
			var t = Oe();
			return ee === null ? (t.memoizedState = e) : Pa(t, ee.memoizedState, e);
		},
		useTransition: () => {
			var e = Kl(tr)[0],
				t = Oe().memoizedState;
			return [e, t];
		},
		useMutableSource: ha,
		useSyncExternalStore: ma,
		useId: Ta,
		unstable_isNewReconciler: !1,
	};
function Ie(e, t) {
	if (e && e.defaultProps) {
		(t = Y({}, t)), (e = e.defaultProps);
		for (var n in e) t[n] === void 0 && (t[n] = e[n]);
		return t;
	}
	return t;
}
function Pi(e, t, n, r) {
	(t = e.memoizedState),
		(n = n(r, t)),
		(n = n == null ? t : Y({}, t, n)),
		(e.memoizedState = n),
		e.lanes === 0 && (e.updateQueue.baseState = n);
}
var vl = {
	isMounted: (e) => ((e = e._reactInternals) ? Ut(e) === e : !1),
	enqueueSetState: (e, t, n) => {
		e = e._reactInternals;
		var r = he(),
			l = yt(e),
			i = qe(r, l);
		(i.payload = t),
			n != null && (i.callback = n),
			(t = mt(e, i, l)),
			t !== null && (Ue(t, e, l, r), zr(t, e, l));
	},
	enqueueReplaceState: (e, t, n) => {
		e = e._reactInternals;
		var r = he(),
			l = yt(e),
			i = qe(r, l);
		(i.tag = 1),
			(i.payload = t),
			n != null && (i.callback = n),
			(t = mt(e, i, l)),
			t !== null && (Ue(t, e, l, r), zr(t, e, l));
	},
	enqueueForceUpdate: (e, t) => {
		e = e._reactInternals;
		var n = he(),
			r = yt(e),
			l = qe(n, r);
		(l.tag = 2),
			t != null && (l.callback = t),
			(t = mt(e, l, r)),
			t !== null && (Ue(t, e, r, n), zr(t, e, r));
	},
};
function js(e, t, n, r, l, i, o) {
	return (
		(e = e.stateNode),
		typeof e.shouldComponentUpdate == "function"
			? e.shouldComponentUpdate(r, i, o)
			: t.prototype && t.prototype.isPureReactComponent
				? !Gn(n, r) || !Gn(l, i)
				: !0
	);
}
function Oa(e, t, n) {
	var r = !1,
		l = St,
		i = t.contextType;
	return (
		typeof i == "object" && i !== null
			? (i = Re(i))
			: ((l = Se(t) ? Ot : de.current),
				(r = t.contextTypes),
				(i = (r = r != null) ? an(e, l) : St)),
		(t = new t(n, i)),
		(e.memoizedState = t.state !== null && t.state !== void 0 ? t.state : null),
		(t.updater = vl),
		(e.stateNode = t),
		(t._reactInternals = e),
		r &&
			((e = e.stateNode),
			(e.__reactInternalMemoizedUnmaskedChildContext = l),
			(e.__reactInternalMemoizedMaskedChildContext = i)),
		t
	);
}
function Ps(e, t, n, r) {
	(e = t.state),
		typeof t.componentWillReceiveProps == "function" &&
			t.componentWillReceiveProps(n, r),
		typeof t.UNSAFE_componentWillReceiveProps == "function" &&
			t.UNSAFE_componentWillReceiveProps(n, r),
		t.state !== e && vl.enqueueReplaceState(t, t.state, null);
}
function Ti(e, t, n, r) {
	var l = e.stateNode;
	(l.props = n), (l.state = e.memoizedState), (l.refs = {}), go(e);
	var i = t.contextType;
	typeof i == "object" && i !== null
		? (l.context = Re(i))
		: ((i = Se(t) ? Ot : de.current), (l.context = an(e, i))),
		(l.state = e.memoizedState),
		(i = t.getDerivedStateFromProps),
		typeof i == "function" && (Pi(e, t, i, n), (l.state = e.memoizedState)),
		typeof t.getDerivedStateFromProps == "function" ||
			typeof l.getSnapshotBeforeUpdate == "function" ||
			(typeof l.UNSAFE_componentWillMount != "function" &&
				typeof l.componentWillMount != "function") ||
			((t = l.state),
			typeof l.componentWillMount == "function" && l.componentWillMount(),
			typeof l.UNSAFE_componentWillMount == "function" &&
				l.UNSAFE_componentWillMount(),
			t !== l.state && vl.enqueueReplaceState(l, l.state, null),
			br(e, n, l, r),
			(l.state = e.memoizedState)),
		typeof l.componentDidMount == "function" && (e.flags |= 4194308);
}
function pn(e, t) {
	try {
		var n = "",
			r = t;
		do (n += $c(r)), (r = r.return);
		while (r);
		var l = n;
	} catch (i) {
		l =
			`
Error generating stack: ` +
			i.message +
			`
` +
			i.stack;
	}
	return { value: e, source: t, stack: l, digest: null };
}
function Ql(e, t, n) {
	return { value: e, source: null, stack: n ?? null, digest: t ?? null };
}
function Li(e, t) {
	try {
		console.error(t.value);
	} catch (n) {
		setTimeout(() => {
			throw n;
		});
	}
}
var hf = typeof WeakMap == "function" ? WeakMap : Map;
function Da(e, t, n) {
	(n = qe(-1, n)), (n.tag = 3), (n.payload = { element: null });
	var r = t.value;
	return (
		(n.callback = () => {
			ll || ((ll = !0), ($i = r)), Li(e, t);
		}),
		n
	);
}
function Ia(e, t, n) {
	(n = qe(-1, n)), (n.tag = 3);
	var r = e.type.getDerivedStateFromError;
	if (typeof r == "function") {
		var l = t.value;
		(n.payload = () => r(l)),
			(n.callback = () => {
				Li(e, t);
			});
	}
	var i = e.stateNode;
	return (
		i !== null &&
			typeof i.componentDidCatch == "function" &&
			(n.callback = function () {
				Li(e, t),
					typeof r != "function" &&
						(vt === null ? (vt = new Set([this])) : vt.add(this));
				var o = t.stack;
				this.componentDidCatch(t.value, {
					componentStack: o !== null ? o : "",
				});
			}),
		n
	);
}
function Ts(e, t, n) {
	var r = e.pingCache;
	if (r === null) {
		r = e.pingCache = new hf();
		var l = new Set();
		r.set(t, l);
	} else (l = r.get(t)), l === void 0 && ((l = new Set()), r.set(t, l));
	l.has(n) || (l.add(n), (e = Pf.bind(null, e, t, n)), t.then(e, e));
}
function Ls(e) {
	do {
		var t;
		if (
			((t = e.tag === 13) &&
				((t = e.memoizedState), (t = t !== null ? t.dehydrated !== null : !0)),
			t)
		)
			return e;
		e = e.return;
	} while (e !== null);
	return null;
}
function zs(e, t, n, r, l) {
	return e.mode & 1
		? ((e.flags |= 65536), (e.lanes = l), e)
		: (e === t
				? (e.flags |= 65536)
				: ((e.flags |= 128),
					(n.flags |= 131072),
					(n.flags &= -52805),
					n.tag === 1 &&
						(n.alternate === null
							? (n.tag = 17)
							: ((t = qe(-1, 1)), (t.tag = 2), mt(n, t, 1))),
					(n.lanes |= 1)),
			e);
}
var mf = rt.ReactCurrentOwner,
	ge = !1;
function pe(e, t, n, r) {
	t.child = e === null ? ca(t, null, n, r) : dn(t, e.child, n, r);
}
function Rs(e, t, n, r, l) {
	n = n.render;
	var i = t.ref;
	return (
		on(t, l),
		(r = No(e, t, n, r, i, l)),
		(n = Eo()),
		e !== null && !ge
			? ((t.updateQueue = e.updateQueue),
				(t.flags &= -2053),
				(e.lanes &= ~l),
				nt(e, t, l))
			: (H && n && co(t), (t.flags |= 1), pe(e, t, r, l), t.child)
	);
}
function Os(e, t, n, r, l) {
	if (e === null) {
		var i = n.type;
		return typeof i == "function" &&
			!Do(i) &&
			i.defaultProps === void 0 &&
			n.compare === null &&
			n.defaultProps === void 0
			? ((t.tag = 15), (t.type = i), Fa(e, t, i, r, l))
			: ((e = Mr(n.type, null, r, t, t.mode, l)),
				(e.ref = t.ref),
				(e.return = t),
				(t.child = e));
	}
	if (((i = e.child), !(e.lanes & l))) {
		var o = i.memoizedProps;
		if (
			((n = n.compare), (n = n !== null ? n : Gn), n(o, r) && e.ref === t.ref)
		)
			return nt(e, t, l);
	}
	return (
		(t.flags |= 1),
		(e = gt(i, r)),
		(e.ref = t.ref),
		(e.return = t),
		(t.child = e)
	);
}
function Fa(e, t, n, r, l) {
	if (e !== null) {
		var i = e.memoizedProps;
		if (Gn(i, r) && e.ref === t.ref)
			if (((ge = !1), (t.pendingProps = r = i), (e.lanes & l) !== 0))
				e.flags & 131072 && (ge = !0);
			else return (t.lanes = e.lanes), nt(e, t, l);
	}
	return zi(e, t, n, r, l);
}
function Ma(e, t, n) {
	var r = t.pendingProps,
		l = r.children,
		i = e !== null ? e.memoizedState : null;
	if (r.mode === "hidden")
		if (!(t.mode & 1))
			(t.memoizedState = { baseLanes: 0, cachePool: null, transitions: null }),
				W(en, xe),
				(xe |= n);
		else {
			if (!(n & 1073741824))
				return (
					(e = i !== null ? i.baseLanes | n : n),
					(t.lanes = t.childLanes = 1073741824),
					(t.memoizedState = {
						baseLanes: e,
						cachePool: null,
						transitions: null,
					}),
					(t.updateQueue = null),
					W(en, xe),
					(xe |= e),
					null
				);
			(t.memoizedState = { baseLanes: 0, cachePool: null, transitions: null }),
				(r = i !== null ? i.baseLanes : n),
				W(en, xe),
				(xe |= r);
		}
	else
		i !== null ? ((r = i.baseLanes | n), (t.memoizedState = null)) : (r = n),
			W(en, xe),
			(xe |= r);
	return pe(e, t, l, n), t.child;
}
function Aa(e, t) {
	var n = t.ref;
	((e === null && n !== null) || (e !== null && e.ref !== n)) &&
		((t.flags |= 512), (t.flags |= 2097152));
}
function zi(e, t, n, r, l) {
	var i = Se(n) ? Ot : de.current;
	return (
		(i = an(t, i)),
		on(t, l),
		(n = No(e, t, n, r, i, l)),
		(r = Eo()),
		e !== null && !ge
			? ((t.updateQueue = e.updateQueue),
				(t.flags &= -2053),
				(e.lanes &= ~l),
				nt(e, t, l))
			: (H && r && co(t), (t.flags |= 1), pe(e, t, n, l), t.child)
	);
}
function Ds(e, t, n, r, l) {
	if (Se(n)) {
		var i = !0;
		Gr(t);
	} else i = !1;
	if ((on(t, l), t.stateNode === null))
		Dr(e, t), Oa(t, n, r), Ti(t, n, r, l), (r = !0);
	else if (e === null) {
		var o = t.stateNode,
			s = t.memoizedProps;
		o.props = s;
		var u = o.context,
			f = n.contextType;
		typeof f == "object" && f !== null
			? (f = Re(f))
			: ((f = Se(n) ? Ot : de.current), (f = an(t, f)));
		var v = n.getDerivedStateFromProps,
			h =
				typeof v == "function" ||
				typeof o.getSnapshotBeforeUpdate == "function";
		h ||
			(typeof o.UNSAFE_componentWillReceiveProps != "function" &&
				typeof o.componentWillReceiveProps != "function") ||
			((s !== r || u !== f) && Ps(t, o, r, f)),
			(ot = !1);
		var m = t.memoizedState;
		(o.state = m),
			br(t, r, o, l),
			(u = t.memoizedState),
			s !== r || m !== u || we.current || ot
				? (typeof v == "function" && (Pi(t, n, v, r), (u = t.memoizedState)),
					(s = ot || js(t, n, s, r, m, u, f))
						? (h ||
								(typeof o.UNSAFE_componentWillMount != "function" &&
									typeof o.componentWillMount != "function") ||
								(typeof o.componentWillMount == "function" &&
									o.componentWillMount(),
								typeof o.UNSAFE_componentWillMount == "function" &&
									o.UNSAFE_componentWillMount()),
							typeof o.componentDidMount == "function" && (t.flags |= 4194308))
						: (typeof o.componentDidMount == "function" && (t.flags |= 4194308),
							(t.memoizedProps = r),
							(t.memoizedState = u)),
					(o.props = r),
					(o.state = u),
					(o.context = f),
					(r = s))
				: (typeof o.componentDidMount == "function" && (t.flags |= 4194308),
					(r = !1));
	} else {
		(o = t.stateNode),
			fa(e, t),
			(s = t.memoizedProps),
			(f = t.type === t.elementType ? s : Ie(t.type, s)),
			(o.props = f),
			(h = t.pendingProps),
			(m = o.context),
			(u = n.contextType),
			typeof u == "object" && u !== null
				? (u = Re(u))
				: ((u = Se(n) ? Ot : de.current), (u = an(t, u)));
		var g = n.getDerivedStateFromProps;
		(v =
			typeof g == "function" ||
			typeof o.getSnapshotBeforeUpdate == "function") ||
			(typeof o.UNSAFE_componentWillReceiveProps != "function" &&
				typeof o.componentWillReceiveProps != "function") ||
			((s !== h || m !== u) && Ps(t, o, r, u)),
			(ot = !1),
			(m = t.memoizedState),
			(o.state = m),
			br(t, r, o, l);
		var x = t.memoizedState;
		s !== h || m !== x || we.current || ot
			? (typeof g == "function" && (Pi(t, n, g, r), (x = t.memoizedState)),
				(f = ot || js(t, n, f, r, m, x, u) || !1)
					? (v ||
							(typeof o.UNSAFE_componentWillUpdate != "function" &&
								typeof o.componentWillUpdate != "function") ||
							(typeof o.componentWillUpdate == "function" &&
								o.componentWillUpdate(r, x, u),
							typeof o.UNSAFE_componentWillUpdate == "function" &&
								o.UNSAFE_componentWillUpdate(r, x, u)),
						typeof o.componentDidUpdate == "function" && (t.flags |= 4),
						typeof o.getSnapshotBeforeUpdate == "function" && (t.flags |= 1024))
					: (typeof o.componentDidUpdate != "function" ||
							(s === e.memoizedProps && m === e.memoizedState) ||
							(t.flags |= 4),
						typeof o.getSnapshotBeforeUpdate != "function" ||
							(s === e.memoizedProps && m === e.memoizedState) ||
							(t.flags |= 1024),
						(t.memoizedProps = r),
						(t.memoizedState = x)),
				(o.props = r),
				(o.state = x),
				(o.context = u),
				(r = f))
			: (typeof o.componentDidUpdate != "function" ||
					(s === e.memoizedProps && m === e.memoizedState) ||
					(t.flags |= 4),
				typeof o.getSnapshotBeforeUpdate != "function" ||
					(s === e.memoizedProps && m === e.memoizedState) ||
					(t.flags |= 1024),
				(r = !1));
	}
	return Ri(e, t, n, r, i, l);
}
function Ri(e, t, n, r, l, i) {
	Aa(e, t);
	var o = (t.flags & 128) !== 0;
	if (!r && !o) return l && ws(t, n, !1), nt(e, t, i);
	(r = t.stateNode), (mf.current = t);
	var s =
		o && typeof n.getDerivedStateFromError != "function" ? null : r.render();
	return (
		(t.flags |= 1),
		e !== null && o
			? ((t.child = dn(t, e.child, null, i)), (t.child = dn(t, null, s, i)))
			: pe(e, t, s, i),
		(t.memoizedState = r.state),
		l && ws(t, n, !0),
		t.child
	);
}
function Ua(e) {
	var t = e.stateNode;
	t.pendingContext
		? gs(e, t.pendingContext, t.pendingContext !== t.context)
		: t.context && gs(e, t.context, !1),
		wo(e, t.containerInfo);
}
function Is(e, t, n, r, l) {
	return cn(), po(l), (t.flags |= 256), pe(e, t, n, r), t.child;
}
var Oi = { dehydrated: null, treeContext: null, retryLane: 0 };
function Di(e) {
	return { baseLanes: e, cachePool: null, transitions: null };
}
function $a(e, t, n) {
	var r = t.pendingProps,
		l = K.current,
		i = !1,
		o = (t.flags & 128) !== 0,
		s;
	if (
		((s = o) ||
			(s = e !== null && e.memoizedState === null ? !1 : (l & 2) !== 0),
		s
			? ((i = !0), (t.flags &= -129))
			: (e === null || e.memoizedState !== null) && (l |= 1),
		W(K, l & 1),
		e === null)
	)
		return (
			_i(t),
			(e = t.memoizedState),
			e !== null && ((e = e.dehydrated), e !== null)
				? (t.mode & 1
						? e.data === "$!"
							? (t.lanes = 8)
							: (t.lanes = 1073741824)
						: (t.lanes = 1),
					null)
				: ((o = r.children),
					(e = r.fallback),
					i
						? ((r = t.mode),
							(i = t.child),
							(o = { mode: "hidden", children: o }),
							!(r & 1) && i !== null
								? ((i.childLanes = 0), (i.pendingProps = o))
								: (i = wl(o, r, 0, null)),
							(e = Rt(e, r, n, null)),
							(i.return = t),
							(e.return = t),
							(i.sibling = e),
							(t.child = i),
							(t.child.memoizedState = Di(n)),
							(t.memoizedState = Oi),
							e)
						: jo(t, o))
		);
	if (((l = e.memoizedState), l !== null && ((s = l.dehydrated), s !== null)))
		return vf(e, t, o, r, s, l, n);
	if (i) {
		(i = r.fallback), (o = t.mode), (l = e.child), (s = l.sibling);
		var u = { mode: "hidden", children: r.children };
		return (
			!(o & 1) && t.child !== l
				? ((r = t.child),
					(r.childLanes = 0),
					(r.pendingProps = u),
					(t.deletions = null))
				: ((r = gt(l, u)), (r.subtreeFlags = l.subtreeFlags & 14680064)),
			s !== null ? (i = gt(s, i)) : ((i = Rt(i, o, n, null)), (i.flags |= 2)),
			(i.return = t),
			(r.return = t),
			(r.sibling = i),
			(t.child = r),
			(r = i),
			(i = t.child),
			(o = e.child.memoizedState),
			(o =
				o === null
					? Di(n)
					: {
							baseLanes: o.baseLanes | n,
							cachePool: null,
							transitions: o.transitions,
						}),
			(i.memoizedState = o),
			(i.childLanes = e.childLanes & ~n),
			(t.memoizedState = Oi),
			r
		);
	}
	return (
		(i = e.child),
		(e = i.sibling),
		(r = gt(i, { mode: "visible", children: r.children })),
		!(t.mode & 1) && (r.lanes = n),
		(r.return = t),
		(r.sibling = null),
		e !== null &&
			((n = t.deletions),
			n === null ? ((t.deletions = [e]), (t.flags |= 16)) : n.push(e)),
		(t.child = r),
		(t.memoizedState = null),
		r
	);
}
function jo(e, t) {
	return (
		(t = wl({ mode: "visible", children: t }, e.mode, 0, null)),
		(t.return = e),
		(e.child = t)
	);
}
function xr(e, t, n, r) {
	return (
		r !== null && po(r),
		dn(t, e.child, null, n),
		(e = jo(t, t.pendingProps.children)),
		(e.flags |= 2),
		(t.memoizedState = null),
		e
	);
}
function vf(e, t, n, r, l, i, o) {
	if (n)
		return t.flags & 256
			? ((t.flags &= -257), (r = Ql(Error(w(422)))), xr(e, t, o, r))
			: t.memoizedState !== null
				? ((t.child = e.child), (t.flags |= 128), null)
				: ((i = r.fallback),
					(l = t.mode),
					(r = wl({ mode: "visible", children: r.children }, l, 0, null)),
					(i = Rt(i, l, o, null)),
					(i.flags |= 2),
					(r.return = t),
					(i.return = t),
					(r.sibling = i),
					(t.child = r),
					t.mode & 1 && dn(t, e.child, null, o),
					(t.child.memoizedState = Di(o)),
					(t.memoizedState = Oi),
					i);
	if (!(t.mode & 1)) return xr(e, t, o, null);
	if (l.data === "$!") {
		if (((r = l.nextSibling && l.nextSibling.dataset), r)) var s = r.dgst;
		return (r = s), (i = Error(w(419))), (r = Ql(i, r, void 0)), xr(e, t, o, r);
	}
	if (((s = (o & e.childLanes) !== 0), ge || s)) {
		if (((r = re), r !== null)) {
			switch (o & -o) {
				case 4:
					l = 2;
					break;
				case 16:
					l = 8;
					break;
				case 64:
				case 128:
				case 256:
				case 512:
				case 1024:
				case 2048:
				case 4096:
				case 8192:
				case 16384:
				case 32768:
				case 65536:
				case 131072:
				case 262144:
				case 524288:
				case 1048576:
				case 2097152:
				case 4194304:
				case 8388608:
				case 16777216:
				case 33554432:
				case 67108864:
					l = 32;
					break;
				case 536870912:
					l = 268435456;
					break;
				default:
					l = 0;
			}
			(l = l & (r.suspendedLanes | o) ? 0 : l),
				l !== 0 &&
					l !== i.retryLane &&
					((i.retryLane = l), tt(e, l), Ue(r, e, l, -1));
		}
		return Oo(), (r = Ql(Error(w(421)))), xr(e, t, o, r);
	}
	return l.data === "$?"
		? ((t.flags |= 128),
			(t.child = e.child),
			(t = Tf.bind(null, e)),
			(l._reactRetry = t),
			null)
		: ((e = i.treeContext),
			(Ne = ht(l.nextSibling)),
			(Ee = t),
			(H = !0),
			(Me = null),
			e !== null &&
				((Pe[Te++] = Ze),
				(Pe[Te++] = Je),
				(Pe[Te++] = Dt),
				(Ze = e.id),
				(Je = e.overflow),
				(Dt = t)),
			(t = jo(t, r.children)),
			(t.flags |= 4096),
			t);
}
function Fs(e, t, n) {
	e.lanes |= t;
	var r = e.alternate;
	r !== null && (r.lanes |= t), ji(e.return, t, n);
}
function Yl(e, t, n, r, l) {
	var i = e.memoizedState;
	i === null
		? (e.memoizedState = {
				isBackwards: t,
				rendering: null,
				renderingStartTime: 0,
				last: r,
				tail: n,
				tailMode: l,
			})
		: ((i.isBackwards = t),
			(i.rendering = null),
			(i.renderingStartTime = 0),
			(i.last = r),
			(i.tail = n),
			(i.tailMode = l));
}
function Wa(e, t, n) {
	var r = t.pendingProps,
		l = r.revealOrder,
		i = r.tail;
	if ((pe(e, t, r.children, n), (r = K.current), r & 2))
		(r = (r & 1) | 2), (t.flags |= 128);
	else {
		if (e !== null && e.flags & 128)
			e: for (e = t.child; e !== null; ) {
				if (e.tag === 13) e.memoizedState !== null && Fs(e, n, t);
				else if (e.tag === 19) Fs(e, n, t);
				else if (e.child !== null) {
					(e.child.return = e), (e = e.child);
					continue;
				}
				if (e === t) break;
				for (; e.sibling === null; ) {
					if (e.return === null || e.return === t) break e;
					e = e.return;
				}
				(e.sibling.return = e.return), (e = e.sibling);
			}
		r &= 1;
	}
	if ((W(K, r), !(t.mode & 1))) t.memoizedState = null;
	else
		switch (l) {
			case "forwards":
				for (n = t.child, l = null; n !== null; )
					(e = n.alternate),
						e !== null && el(e) === null && (l = n),
						(n = n.sibling);
				(n = l),
					n === null
						? ((l = t.child), (t.child = null))
						: ((l = n.sibling), (n.sibling = null)),
					Yl(t, !1, l, n, i);
				break;
			case "backwards":
				for (n = null, l = t.child, t.child = null; l !== null; ) {
					if (((e = l.alternate), e !== null && el(e) === null)) {
						t.child = l;
						break;
					}
					(e = l.sibling), (l.sibling = n), (n = l), (l = e);
				}
				Yl(t, !0, n, null, i);
				break;
			case "together":
				Yl(t, !1, null, null, void 0);
				break;
			default:
				t.memoizedState = null;
		}
	return t.child;
}
function Dr(e, t) {
	!(t.mode & 1) &&
		e !== null &&
		((e.alternate = null), (t.alternate = null), (t.flags |= 2));
}
function nt(e, t, n) {
	if (
		(e !== null && (t.dependencies = e.dependencies),
		(Ft |= t.lanes),
		!(n & t.childLanes))
	)
		return null;
	if (e !== null && t.child !== e.child) throw Error(w(153));
	if (t.child !== null) {
		for (
			e = t.child, n = gt(e, e.pendingProps), t.child = n, n.return = t;
			e.sibling !== null;
		)
			(e = e.sibling), (n = n.sibling = gt(e, e.pendingProps)), (n.return = t);
		n.sibling = null;
	}
	return t.child;
}
function yf(e, t, n) {
	switch (t.tag) {
		case 3:
			Ua(t), cn();
			break;
		case 5:
			pa(t);
			break;
		case 1:
			Se(t.type) && Gr(t);
			break;
		case 4:
			wo(t, t.stateNode.containerInfo);
			break;
		case 10: {
			var r = t.type._context,
				l = t.memoizedProps.value;
			W(Jr, r._currentValue), (r._currentValue = l);
			break;
		}
		case 13:
			if (((r = t.memoizedState), r !== null))
				return r.dehydrated !== null
					? (W(K, K.current & 1), (t.flags |= 128), null)
					: n & t.child.childLanes
						? $a(e, t, n)
						: (W(K, K.current & 1),
							(e = nt(e, t, n)),
							e !== null ? e.sibling : null);
			W(K, K.current & 1);
			break;
		case 19:
			if (((r = (n & t.childLanes) !== 0), e.flags & 128)) {
				if (r) return Wa(e, t, n);
				t.flags |= 128;
			}
			if (
				((l = t.memoizedState),
				l !== null &&
					((l.rendering = null), (l.tail = null), (l.lastEffect = null)),
				W(K, K.current),
				r)
			)
				break;
			return null;
		case 22:
		case 23:
			return (t.lanes = 0), Ma(e, t, n);
	}
	return nt(e, t, n);
}
var Ba, Ii, Va, Ha;
Ba = (e, t) => {
	for (var n = t.child; n !== null; ) {
		if (n.tag === 5 || n.tag === 6) e.appendChild(n.stateNode);
		else if (n.tag !== 4 && n.child !== null) {
			(n.child.return = n), (n = n.child);
			continue;
		}
		if (n === t) break;
		for (; n.sibling === null; ) {
			if (n.return === null || n.return === t) return;
			n = n.return;
		}
		(n.sibling.return = n.return), (n = n.sibling);
	}
};
Ii = () => {};
Va = (e, t, n, r) => {
	var l = e.memoizedProps;
	if (l !== r) {
		(e = t.stateNode), Lt(Qe.current);
		var i = null;
		switch (n) {
			case "input":
				(l = ri(e, l)), (r = ri(e, r)), (i = []);
				break;
			case "select":
				(l = Y({}, l, { value: void 0 })),
					(r = Y({}, r, { value: void 0 })),
					(i = []);
				break;
			case "textarea":
				(l = oi(e, l)), (r = oi(e, r)), (i = []);
				break;
			default:
				typeof l.onClick != "function" &&
					typeof r.onClick == "function" &&
					(e.onclick = Qr);
		}
		ui(n, r);
		var o;
		n = null;
		for (f in l)
			if (!Object.hasOwn(r, f) && Object.hasOwn(l, f) && l[f] != null)
				if (f === "style") {
					var s = l[f];
					for (o in s) Object.hasOwn(s, o) && (n || (n = {}), (n[o] = ""));
				} else
					f !== "dangerouslySetInnerHTML" &&
						f !== "children" &&
						f !== "suppressContentEditableWarning" &&
						f !== "suppressHydrationWarning" &&
						f !== "autoFocus" &&
						(Object.hasOwn(Wn, f)
							? i || (i = [])
							: (i = i || []).push(f, null));
		for (f in r) {
			var u = r[f];
			if (
				((s = l != null ? l[f] : void 0),
				Object.hasOwn(r, f) && u !== s && (u != null || s != null))
			)
				if (f === "style")
					if (s) {
						for (o in s)
							!Object.hasOwn(s, o) ||
								(u && Object.hasOwn(u, o)) ||
								(n || (n = {}), (n[o] = ""));
						for (o in u)
							Object.hasOwn(u, o) &&
								s[o] !== u[o] &&
								(n || (n = {}), (n[o] = u[o]));
					} else n || (i || (i = []), i.push(f, n)), (n = u);
				else
					f === "dangerouslySetInnerHTML"
						? ((u = u ? u.__html : void 0),
							(s = s ? s.__html : void 0),
							u != null && s !== u && (i = i || []).push(f, u))
						: f === "children"
							? (typeof u != "string" && typeof u != "number") ||
								(i = i || []).push(f, "" + u)
							: f !== "suppressContentEditableWarning" &&
								f !== "suppressHydrationWarning" &&
								(Object.hasOwn(Wn, f)
									? (u != null && f === "onScroll" && B("scroll", e),
										i || s === u || (i = []))
									: (i = i || []).push(f, u));
		}
		n && (i = i || []).push("style", n);
		var f = i;
		(t.updateQueue = f) && (t.flags |= 4);
	}
};
Ha = (e, t, n, r) => {
	n !== r && (t.flags |= 4);
};
function _n(e, t) {
	if (!H)
		switch (e.tailMode) {
			case "hidden":
				t = e.tail;
				for (var n = null; t !== null; )
					t.alternate !== null && (n = t), (t = t.sibling);
				n === null ? (e.tail = null) : (n.sibling = null);
				break;
			case "collapsed":
				n = e.tail;
				for (var r = null; n !== null; )
					n.alternate !== null && (r = n), (n = n.sibling);
				r === null
					? t || e.tail === null
						? (e.tail = null)
						: (e.tail.sibling = null)
					: (r.sibling = null);
		}
}
function ae(e) {
	var t = e.alternate !== null && e.alternate.child === e.child,
		n = 0,
		r = 0;
	if (t)
		for (var l = e.child; l !== null; )
			(n |= l.lanes | l.childLanes),
				(r |= l.subtreeFlags & 14680064),
				(r |= l.flags & 14680064),
				(l.return = e),
				(l = l.sibling);
	else
		for (l = e.child; l !== null; )
			(n |= l.lanes | l.childLanes),
				(r |= l.subtreeFlags),
				(r |= l.flags),
				(l.return = e),
				(l = l.sibling);
	return (e.subtreeFlags |= r), (e.childLanes = n), t;
}
function gf(e, t, n) {
	var r = t.pendingProps;
	switch ((fo(t), t.tag)) {
		case 2:
		case 16:
		case 15:
		case 0:
		case 11:
		case 7:
		case 8:
		case 12:
		case 9:
		case 14:
			return ae(t), null;
		case 1:
			return Se(t.type) && Yr(), ae(t), null;
		case 3:
			return (
				(r = t.stateNode),
				fn(),
				V(we),
				V(de),
				ko(),
				r.pendingContext &&
					((r.context = r.pendingContext), (r.pendingContext = null)),
				(e === null || e.child === null) &&
					(Sr(t)
						? (t.flags |= 4)
						: e === null ||
							(e.memoizedState.isDehydrated && !(t.flags & 256)) ||
							((t.flags |= 1024), Me !== null && (Vi(Me), (Me = null)))),
				Ii(e, t),
				ae(t),
				null
			);
		case 5: {
			So(t);
			var l = Lt(bn.current);
			if (((n = t.type), e !== null && t.stateNode != null))
				Va(e, t, n, r, l),
					e.ref !== t.ref && ((t.flags |= 512), (t.flags |= 2097152));
			else {
				if (!r) {
					if (t.stateNode === null) throw Error(w(166));
					return ae(t), null;
				}
				if (((e = Lt(Qe.current)), Sr(t))) {
					(r = t.stateNode), (n = t.type);
					var i = t.memoizedProps;
					switch (((r[He] = t), (r[Jn] = i), (e = (t.mode & 1) !== 0), n)) {
						case "dialog":
							B("cancel", r), B("close", r);
							break;
						case "iframe":
						case "object":
						case "embed":
							B("load", r);
							break;
						case "video":
						case "audio":
							for (l = 0; l < zn.length; l++) B(zn[l], r);
							break;
						case "source":
							B("error", r);
							break;
						case "img":
						case "image":
						case "link":
							B("error", r), B("load", r);
							break;
						case "details":
							B("toggle", r);
							break;
						case "input":
							Ko(r, i), B("invalid", r);
							break;
						case "select":
							(r._wrapperState = { wasMultiple: !!i.multiple }),
								B("invalid", r);
							break;
						case "textarea":
							Yo(r, i), B("invalid", r);
					}
					ui(n, i), (l = null);
					for (var o in i)
						if (Object.hasOwn(i, o)) {
							var s = i[o];
							o === "children"
								? typeof s == "string"
									? r.textContent !== s &&
										(i.suppressHydrationWarning !== !0 &&
											wr(r.textContent, s, e),
										(l = ["children", s]))
									: typeof s == "number" &&
										r.textContent !== "" + s &&
										(i.suppressHydrationWarning !== !0 &&
											wr(r.textContent, s, e),
										(l = ["children", "" + s]))
								: Object.hasOwn(Wn, o) &&
									s != null &&
									o === "onScroll" &&
									B("scroll", r);
						}
					switch (n) {
						case "input":
							dr(r), Qo(r, i, !0);
							break;
						case "textarea":
							dr(r), Go(r);
							break;
						case "select":
						case "option":
							break;
						default:
							typeof i.onClick == "function" && (r.onclick = Qr);
					}
					(r = l), (t.updateQueue = r), r !== null && (t.flags |= 4);
				} else {
					(o = l.nodeType === 9 ? l : l.ownerDocument),
						e === "http://www.w3.org/1999/xhtml" && (e = gu(n)),
						e === "http://www.w3.org/1999/xhtml"
							? n === "script"
								? ((e = o.createElement("div")),
									(e.innerHTML = "<script></script>"),
									(e = e.removeChild(e.firstChild)))
								: typeof r.is == "string"
									? (e = o.createElement(n, { is: r.is }))
									: ((e = o.createElement(n)),
										n === "select" &&
											((o = e),
											r.multiple
												? (o.multiple = !0)
												: r.size && (o.size = r.size)))
							: (e = o.createElementNS(e, n)),
						(e[He] = t),
						(e[Jn] = r),
						Ba(e, t, !1, !1),
						(t.stateNode = e);
					e: {
						switch (((o = ai(n, r)), n)) {
							case "dialog":
								B("cancel", e), B("close", e), (l = r);
								break;
							case "iframe":
							case "object":
							case "embed":
								B("load", e), (l = r);
								break;
							case "video":
							case "audio":
								for (l = 0; l < zn.length; l++) B(zn[l], e);
								l = r;
								break;
							case "source":
								B("error", e), (l = r);
								break;
							case "img":
							case "image":
							case "link":
								B("error", e), B("load", e), (l = r);
								break;
							case "details":
								B("toggle", e), (l = r);
								break;
							case "input":
								Ko(e, r), (l = ri(e, r)), B("invalid", e);
								break;
							case "option":
								l = r;
								break;
							case "select":
								(e._wrapperState = { wasMultiple: !!r.multiple }),
									(l = Y({}, r, { value: void 0 })),
									B("invalid", e);
								break;
							case "textarea":
								Yo(e, r), (l = oi(e, r)), B("invalid", e);
								break;
							default:
								l = r;
						}
						ui(n, l), (s = l);
						for (i in s)
							if (Object.hasOwn(s, i)) {
								var u = s[i];
								i === "style"
									? ku(e, u)
									: i === "dangerouslySetInnerHTML"
										? ((u = u ? u.__html : void 0), u != null && wu(e, u))
										: i === "children"
											? typeof u == "string"
												? (n !== "textarea" || u !== "") && Bn(e, u)
												: typeof u == "number" && Bn(e, "" + u)
											: i !== "suppressContentEditableWarning" &&
												i !== "suppressHydrationWarning" &&
												i !== "autoFocus" &&
												(Object.hasOwn(Wn, i)
													? u != null && i === "onScroll" && B("scroll", e)
													: u != null && Zi(e, i, u, o));
							}
						switch (n) {
							case "input":
								dr(e), Qo(e, r, !1);
								break;
							case "textarea":
								dr(e), Go(e);
								break;
							case "option":
								r.value != null && e.setAttribute("value", "" + wt(r.value));
								break;
							case "select":
								(e.multiple = !!r.multiple),
									(i = r.value),
									i != null
										? tn(e, !!r.multiple, i, !1)
										: r.defaultValue != null &&
											tn(e, !!r.multiple, r.defaultValue, !0);
								break;
							default:
								typeof l.onClick == "function" && (e.onclick = Qr);
						}
						switch (n) {
							case "button":
							case "input":
							case "select":
							case "textarea":
								r = !!r.autoFocus;
								break e;
							case "img":
								r = !0;
								break e;
							default:
								r = !1;
						}
					}
					r && (t.flags |= 4);
				}
				t.ref !== null && ((t.flags |= 512), (t.flags |= 2097152));
			}
			return ae(t), null;
		}
		case 6:
			if (e && t.stateNode != null) Ha(e, t, e.memoizedProps, r);
			else {
				if (typeof r != "string" && t.stateNode === null) throw Error(w(166));
				if (((n = Lt(bn.current)), Lt(Qe.current), Sr(t))) {
					if (
						((r = t.stateNode),
						(n = t.memoizedProps),
						(r[He] = t),
						(i = r.nodeValue !== n) && ((e = Ee), e !== null))
					)
						switch (e.tag) {
							case 3:
								wr(r.nodeValue, n, (e.mode & 1) !== 0);
								break;
							case 5:
								e.memoizedProps.suppressHydrationWarning !== !0 &&
									wr(r.nodeValue, n, (e.mode & 1) !== 0);
						}
					i && (t.flags |= 4);
				} else
					(r = (n.nodeType === 9 ? n : n.ownerDocument).createTextNode(r)),
						(r[He] = t),
						(t.stateNode = r);
			}
			return ae(t), null;
		case 13:
			if (
				(V(K),
				(r = t.memoizedState),
				e === null ||
					(e.memoizedState !== null && e.memoizedState.dehydrated !== null))
			) {
				if (H && Ne !== null && t.mode & 1 && !(t.flags & 128))
					ua(), cn(), (t.flags |= 98560), (i = !1);
				else if (((i = Sr(t)), r !== null && r.dehydrated !== null)) {
					if (e === null) {
						if (!i) throw Error(w(318));
						if (
							((i = t.memoizedState),
							(i = i !== null ? i.dehydrated : null),
							!i)
						)
							throw Error(w(317));
						i[He] = t;
					} else
						cn(), !(t.flags & 128) && (t.memoizedState = null), (t.flags |= 4);
					ae(t), (i = !1);
				} else Me !== null && (Vi(Me), (Me = null)), (i = !0);
				if (!i) return t.flags & 65536 ? t : null;
			}
			return t.flags & 128
				? ((t.lanes = n), t)
				: ((r = r !== null),
					r !== (e !== null && e.memoizedState !== null) &&
						r &&
						((t.child.flags |= 8192),
						t.mode & 1 &&
							(e === null || K.current & 1 ? te === 0 && (te = 3) : Oo())),
					t.updateQueue !== null && (t.flags |= 4),
					ae(t),
					null);
		case 4:
			return (
				fn(), Ii(e, t), e === null && Xn(t.stateNode.containerInfo), ae(t), null
			);
		case 10:
			return vo(t.type._context), ae(t), null;
		case 17:
			return Se(t.type) && Yr(), ae(t), null;
		case 19:
			if ((V(K), (i = t.memoizedState), i === null)) return ae(t), null;
			if (((r = (t.flags & 128) !== 0), (o = i.rendering), o === null))
				if (r) _n(i, !1);
				else {
					if (te !== 0 || (e !== null && e.flags & 128))
						for (e = t.child; e !== null; ) {
							if (((o = el(e)), o !== null)) {
								for (
									t.flags |= 128,
										_n(i, !1),
										r = o.updateQueue,
										r !== null && ((t.updateQueue = r), (t.flags |= 4)),
										t.subtreeFlags = 0,
										r = n,
										n = t.child;
									n !== null;
								)
									(i = n),
										(e = r),
										(i.flags &= 14680066),
										(o = i.alternate),
										o === null
											? ((i.childLanes = 0),
												(i.lanes = e),
												(i.child = null),
												(i.subtreeFlags = 0),
												(i.memoizedProps = null),
												(i.memoizedState = null),
												(i.updateQueue = null),
												(i.dependencies = null),
												(i.stateNode = null))
											: ((i.childLanes = o.childLanes),
												(i.lanes = o.lanes),
												(i.child = o.child),
												(i.subtreeFlags = 0),
												(i.deletions = null),
												(i.memoizedProps = o.memoizedProps),
												(i.memoizedState = o.memoizedState),
												(i.updateQueue = o.updateQueue),
												(i.type = o.type),
												(e = o.dependencies),
												(i.dependencies =
													e === null
														? null
														: {
																lanes: e.lanes,
																firstContext: e.firstContext,
															})),
										(n = n.sibling);
								return W(K, (K.current & 1) | 2), t.child;
							}
							e = e.sibling;
						}
					i.tail !== null &&
						J() > hn &&
						((t.flags |= 128), (r = !0), _n(i, !1), (t.lanes = 4194304));
				}
			else {
				if (!r)
					if (((e = el(o)), e !== null)) {
						if (
							((t.flags |= 128),
							(r = !0),
							(n = e.updateQueue),
							n !== null && ((t.updateQueue = n), (t.flags |= 4)),
							_n(i, !0),
							i.tail === null && i.tailMode === "hidden" && !o.alternate && !H)
						)
							return ae(t), null;
					} else
						2 * J() - i.renderingStartTime > hn &&
							n !== 1073741824 &&
							((t.flags |= 128), (r = !0), _n(i, !1), (t.lanes = 4194304));
				i.isBackwards
					? ((o.sibling = t.child), (t.child = o))
					: ((n = i.last),
						n !== null ? (n.sibling = o) : (t.child = o),
						(i.last = o));
			}
			return i.tail !== null
				? ((t = i.tail),
					(i.rendering = t),
					(i.tail = t.sibling),
					(i.renderingStartTime = J()),
					(t.sibling = null),
					(n = K.current),
					W(K, r ? (n & 1) | 2 : n & 1),
					t)
				: (ae(t), null);
		case 22:
		case 23:
			return (
				Ro(),
				(r = t.memoizedState !== null),
				e !== null && (e.memoizedState !== null) !== r && (t.flags |= 8192),
				r && t.mode & 1
					? xe & 1073741824 && (ae(t), t.subtreeFlags & 6 && (t.flags |= 8192))
					: ae(t),
				null
			);
		case 24:
			return null;
		case 25:
			return null;
	}
	throw Error(w(156, t.tag));
}
function wf(e, t) {
	switch ((fo(t), t.tag)) {
		case 1:
			return (
				Se(t.type) && Yr(),
				(e = t.flags),
				e & 65536 ? ((t.flags = (e & -65537) | 128), t) : null
			);
		case 3:
			return (
				fn(),
				V(we),
				V(de),
				ko(),
				(e = t.flags),
				e & 65536 && !(e & 128) ? ((t.flags = (e & -65537) | 128), t) : null
			);
		case 5:
			return So(t), null;
		case 13:
			if ((V(K), (e = t.memoizedState), e !== null && e.dehydrated !== null)) {
				if (t.alternate === null) throw Error(w(340));
				cn();
			}
			return (
				(e = t.flags), e & 65536 ? ((t.flags = (e & -65537) | 128), t) : null
			);
		case 19:
			return V(K), null;
		case 4:
			return fn(), null;
		case 10:
			return vo(t.type._context), null;
		case 22:
		case 23:
			return Ro(), null;
		case 24:
			return null;
		default:
			return null;
	}
}
var Nr = !1,
	ce = !1,
	Sf = typeof WeakSet == "function" ? WeakSet : Set,
	T = null;
function bt(e, t) {
	var n = e.ref;
	if (n !== null)
		if (typeof n == "function")
			try {
				n(null);
			} catch (r) {
				X(e, t, r);
			}
		else n.current = null;
}
function Fi(e, t, n) {
	try {
		n();
	} catch (r) {
		X(e, t, r);
	}
}
var Ms = !1;
function kf(e, t) {
	if (((wi = Vr), (e = Xu()), ao(e))) {
		if ("selectionStart" in e)
			var n = { start: e.selectionStart, end: e.selectionEnd };
		else
			e: {
				n = ((n = e.ownerDocument) && n.defaultView) || window;
				var r = n.getSelection && n.getSelection();
				if (r && r.rangeCount !== 0) {
					n = r.anchorNode;
					var l = r.anchorOffset,
						i = r.focusNode;
					r = r.focusOffset;
					try {
						n.nodeType, i.nodeType;
					} catch {
						n = null;
						break e;
					}
					var o = 0,
						s = -1,
						u = -1,
						f = 0,
						v = 0,
						h = e,
						m = null;
					t: for (;;) {
						for (
							var g;
							h !== n || (l !== 0 && h.nodeType !== 3) || (s = o + l),
								h !== i || (r !== 0 && h.nodeType !== 3) || (u = o + r),
								h.nodeType === 3 && (o += h.nodeValue.length),
								(g = h.firstChild) !== null;
						)
							(m = h), (h = g);
						for (;;) {
							if (h === e) break t;
							if (
								(m === n && ++f === l && (s = o),
								m === i && ++v === r && (u = o),
								(g = h.nextSibling) !== null)
							)
								break;
							(h = m), (m = h.parentNode);
						}
						h = g;
					}
					n = s === -1 || u === -1 ? null : { start: s, end: u };
				} else n = null;
			}
		n = n || { start: 0, end: 0 };
	} else n = null;
	for (Si = { focusedElem: e, selectionRange: n }, Vr = !1, T = t; T !== null; )
		if (((t = T), (e = t.child), (t.subtreeFlags & 1028) !== 0 && e !== null))
			(e.return = t), (T = e);
		else
			for (; T !== null; ) {
				t = T;
				try {
					var x = t.alternate;
					if (t.flags & 1024)
						switch (t.tag) {
							case 0:
							case 11:
							case 15:
								break;
							case 1:
								if (x !== null) {
									var E = x.memoizedProps,
										D = x.memoizedState,
										p = t.stateNode,
										a = p.getSnapshotBeforeUpdate(
											t.elementType === t.type ? E : Ie(t.type, E),
											D,
										);
									p.__reactInternalSnapshotBeforeUpdate = a;
								}
								break;
							case 3: {
								var d = t.stateNode.containerInfo;
								d.nodeType === 1
									? (d.textContent = "")
									: d.nodeType === 9 &&
										d.documentElement &&
										d.removeChild(d.documentElement);
								break;
							}
							case 5:
							case 6:
							case 4:
							case 17:
								break;
							default:
								throw Error(w(163));
						}
				} catch (y) {
					X(t, t.return, y);
				}
				if (((e = t.sibling), e !== null)) {
					(e.return = t.return), (T = e);
					break;
				}
				T = t.return;
			}
	return (x = Ms), (Ms = !1), x;
}
function An(e, t, n) {
	var r = t.updateQueue;
	if (((r = r !== null ? r.lastEffect : null), r !== null)) {
		var l = (r = r.next);
		do {
			if ((l.tag & e) === e) {
				var i = l.destroy;
				(l.destroy = void 0), i !== void 0 && Fi(t, n, i);
			}
			l = l.next;
		} while (l !== r);
	}
}
function yl(e, t) {
	if (
		((t = t.updateQueue), (t = t !== null ? t.lastEffect : null), t !== null)
	) {
		var n = (t = t.next);
		do {
			if ((n.tag & e) === e) {
				var r = n.create;
				n.destroy = r();
			}
			n = n.next;
		} while (n !== t);
	}
}
function Mi(e) {
	var t = e.ref;
	if (t !== null) {
		var n = e.stateNode;
		switch (e.tag) {
			case 5:
				e = n;
				break;
			default:
				e = n;
		}
		typeof t == "function" ? t(e) : (t.current = e);
	}
}
function Ka(e) {
	var t = e.alternate;
	t !== null && ((e.alternate = null), Ka(t)),
		(e.child = null),
		(e.deletions = null),
		(e.sibling = null),
		e.tag === 5 &&
			((t = e.stateNode),
			t !== null &&
				(delete t[He], delete t[Jn], delete t[Ni], delete t[nf], delete t[rf])),
		(e.stateNode = null),
		(e.return = null),
		(e.dependencies = null),
		(e.memoizedProps = null),
		(e.memoizedState = null),
		(e.pendingProps = null),
		(e.stateNode = null),
		(e.updateQueue = null);
}
function Qa(e) {
	return e.tag === 5 || e.tag === 3 || e.tag === 4;
}
function As(e) {
	e: for (;;) {
		for (; e.sibling === null; ) {
			if (e.return === null || Qa(e.return)) return null;
			e = e.return;
		}
		for (
			e.sibling.return = e.return, e = e.sibling;
			e.tag !== 5 && e.tag !== 6 && e.tag !== 18;
		) {
			if (e.flags & 2 || e.child === null || e.tag === 4) continue e;
			(e.child.return = e), (e = e.child);
		}
		if (!(e.flags & 2)) return e.stateNode;
	}
}
function Ai(e, t, n) {
	var r = e.tag;
	if (r === 5 || r === 6)
		(e = e.stateNode),
			t
				? n.nodeType === 8
					? n.parentNode.insertBefore(e, t)
					: n.insertBefore(e, t)
				: (n.nodeType === 8
						? ((t = n.parentNode), t.insertBefore(e, n))
						: ((t = n), t.appendChild(e)),
					(n = n._reactRootContainer),
					n != null || t.onclick !== null || (t.onclick = Qr));
	else if (r !== 4 && ((e = e.child), e !== null))
		for (Ai(e, t, n), e = e.sibling; e !== null; ) Ai(e, t, n), (e = e.sibling);
}
function Ui(e, t, n) {
	var r = e.tag;
	if (r === 5 || r === 6)
		(e = e.stateNode), t ? n.insertBefore(e, t) : n.appendChild(e);
	else if (r !== 4 && ((e = e.child), e !== null))
		for (Ui(e, t, n), e = e.sibling; e !== null; ) Ui(e, t, n), (e = e.sibling);
}
var ie = null,
	Fe = !1;
function lt(e, t, n) {
	for (n = n.child; n !== null; ) Ya(e, t, n), (n = n.sibling);
}
function Ya(e, t, n) {
	if (Ke && typeof Ke.onCommitFiberUnmount == "function")
		try {
			Ke.onCommitFiberUnmount(al, n);
		} catch {}
	switch (n.tag) {
		case 5:
			ce || bt(n, t);
		case 6: {
			var r = ie,
				l = Fe;
			(ie = null),
				lt(e, t, n),
				(ie = r),
				(Fe = l),
				ie !== null &&
					(Fe
						? ((e = ie),
							(n = n.stateNode),
							e.nodeType === 8 ? e.parentNode.removeChild(n) : e.removeChild(n))
						: ie.removeChild(n.stateNode));
			break;
		}
		case 18:
			ie !== null &&
				(Fe
					? ((e = ie),
						(n = n.stateNode),
						e.nodeType === 8
							? $l(e.parentNode, n)
							: e.nodeType === 1 && $l(e, n),
						Qn(e))
					: $l(ie, n.stateNode));
			break;
		case 4:
			(r = ie),
				(l = Fe),
				(ie = n.stateNode.containerInfo),
				(Fe = !0),
				lt(e, t, n),
				(ie = r),
				(Fe = l);
			break;
		case 0:
		case 11:
		case 14:
		case 15:
			if (
				!ce &&
				((r = n.updateQueue), r !== null && ((r = r.lastEffect), r !== null))
			) {
				l = r = r.next;
				do {
					var i = l,
						o = i.destroy;
					(i = i.tag),
						o !== void 0 && (i & 2 || i & 4) && Fi(n, t, o),
						(l = l.next);
				} while (l !== r);
			}
			lt(e, t, n);
			break;
		case 1:
			if (
				!ce &&
				(bt(n, t),
				(r = n.stateNode),
				typeof r.componentWillUnmount == "function")
			)
				try {
					(r.props = n.memoizedProps),
						(r.state = n.memoizedState),
						r.componentWillUnmount();
				} catch (s) {
					X(n, t, s);
				}
			lt(e, t, n);
			break;
		case 21:
			lt(e, t, n);
			break;
		case 22:
			n.mode & 1
				? ((ce = (r = ce) || n.memoizedState !== null), lt(e, t, n), (ce = r))
				: lt(e, t, n);
			break;
		default:
			lt(e, t, n);
	}
}
function Us(e) {
	var t = e.updateQueue;
	if (t !== null) {
		e.updateQueue = null;
		var n = e.stateNode;
		n === null && (n = e.stateNode = new Sf()),
			t.forEach((r) => {
				var l = Lf.bind(null, e, r);
				n.has(r) || (n.add(r), r.then(l, l));
			});
	}
}
function De(e, t) {
	var n = t.deletions;
	if (n !== null)
		for (var r = 0; r < n.length; r++) {
			var l = n[r];
			try {
				var i = e,
					o = t,
					s = o;
				e: for (; s !== null; ) {
					switch (s.tag) {
						case 5:
							(ie = s.stateNode), (Fe = !1);
							break e;
						case 3:
							(ie = s.stateNode.containerInfo), (Fe = !0);
							break e;
						case 4:
							(ie = s.stateNode.containerInfo), (Fe = !0);
							break e;
					}
					s = s.return;
				}
				if (ie === null) throw Error(w(160));
				Ya(i, o, l), (ie = null), (Fe = !1);
				var u = l.alternate;
				u !== null && (u.return = null), (l.return = null);
			} catch (f) {
				X(l, t, f);
			}
		}
	if (t.subtreeFlags & 12854)
		for (t = t.child; t !== null; ) Ga(t, e), (t = t.sibling);
}
function Ga(e, t) {
	var n = e.alternate,
		r = e.flags;
	switch (e.tag) {
		case 0:
		case 11:
		case 14:
		case 15:
			if ((De(t, e), Be(e), r & 4)) {
				try {
					An(3, e, e.return), yl(3, e);
				} catch (E) {
					X(e, e.return, E);
				}
				try {
					An(5, e, e.return);
				} catch (E) {
					X(e, e.return, E);
				}
			}
			break;
		case 1:
			De(t, e), Be(e), r & 512 && n !== null && bt(n, n.return);
			break;
		case 5:
			if (
				(De(t, e),
				Be(e),
				r & 512 && n !== null && bt(n, n.return),
				e.flags & 32)
			) {
				var l = e.stateNode;
				try {
					Bn(l, "");
				} catch (E) {
					X(e, e.return, E);
				}
			}
			if (r & 4 && ((l = e.stateNode), l != null)) {
				var i = e.memoizedProps,
					o = n !== null ? n.memoizedProps : i,
					s = e.type,
					u = e.updateQueue;
				if (((e.updateQueue = null), u !== null))
					try {
						s === "input" && i.type === "radio" && i.name != null && vu(l, i),
							ai(s, o);
						var f = ai(s, i);
						for (o = 0; o < u.length; o += 2) {
							var v = u[o],
								h = u[o + 1];
							v === "style"
								? ku(l, h)
								: v === "dangerouslySetInnerHTML"
									? wu(l, h)
									: v === "children"
										? Bn(l, h)
										: Zi(l, v, h, f);
						}
						switch (s) {
							case "input":
								li(l, i);
								break;
							case "textarea":
								yu(l, i);
								break;
							case "select": {
								var m = l._wrapperState.wasMultiple;
								l._wrapperState.wasMultiple = !!i.multiple;
								var g = i.value;
								g != null
									? tn(l, !!i.multiple, g, !1)
									: m !== !!i.multiple &&
										(i.defaultValue != null
											? tn(l, !!i.multiple, i.defaultValue, !0)
											: tn(l, !!i.multiple, i.multiple ? [] : "", !1));
							}
						}
						l[Jn] = i;
					} catch (E) {
						X(e, e.return, E);
					}
			}
			break;
		case 6:
			if ((De(t, e), Be(e), r & 4)) {
				if (e.stateNode === null) throw Error(w(162));
				(l = e.stateNode), (i = e.memoizedProps);
				try {
					l.nodeValue = i;
				} catch (E) {
					X(e, e.return, E);
				}
			}
			break;
		case 3:
			if (
				(De(t, e), Be(e), r & 4 && n !== null && n.memoizedState.isDehydrated)
			)
				try {
					Qn(t.containerInfo);
				} catch (E) {
					X(e, e.return, E);
				}
			break;
		case 4:
			De(t, e), Be(e);
			break;
		case 13:
			De(t, e),
				Be(e),
				(l = e.child),
				l.flags & 8192 &&
					((i = l.memoizedState !== null),
					(l.stateNode.isHidden = i),
					!i ||
						(l.alternate !== null && l.alternate.memoizedState !== null) ||
						(Lo = J())),
				r & 4 && Us(e);
			break;
		case 22:
			if (
				((v = n !== null && n.memoizedState !== null),
				e.mode & 1 ? ((ce = (f = ce) || v), De(t, e), (ce = f)) : De(t, e),
				Be(e),
				r & 8192)
			) {
				if (
					((f = e.memoizedState !== null),
					(e.stateNode.isHidden = f) && !v && e.mode & 1)
				)
					for (T = e, v = e.child; v !== null; ) {
						for (h = T = v; T !== null; ) {
							switch (((m = T), (g = m.child), m.tag)) {
								case 0:
								case 11:
								case 14:
								case 15:
									An(4, m, m.return);
									break;
								case 1: {
									bt(m, m.return);
									var x = m.stateNode;
									if (typeof x.componentWillUnmount == "function") {
										(r = m), (n = m.return);
										try {
											(t = r),
												(x.props = t.memoizedProps),
												(x.state = t.memoizedState),
												x.componentWillUnmount();
										} catch (E) {
											X(r, n, E);
										}
									}
									break;
								}
								case 5:
									bt(m, m.return);
									break;
								case 22:
									if (m.memoizedState !== null) {
										Ws(h);
										continue;
									}
							}
							g !== null ? ((g.return = m), (T = g)) : Ws(h);
						}
						v = v.sibling;
					}
				e: for (v = null, h = e; ; ) {
					if (h.tag === 5) {
						if (v === null) {
							v = h;
							try {
								(l = h.stateNode),
									f
										? ((i = l.style),
											typeof i.setProperty == "function"
												? i.setProperty("display", "none", "important")
												: (i.display = "none"))
										: ((s = h.stateNode),
											(u = h.memoizedProps.style),
											(o =
												u != null && Object.hasOwn(u, "display")
													? u.display
													: null),
											(s.style.display = Su("display", o)));
							} catch (E) {
								X(e, e.return, E);
							}
						}
					} else if (h.tag === 6) {
						if (v === null)
							try {
								h.stateNode.nodeValue = f ? "" : h.memoizedProps;
							} catch (E) {
								X(e, e.return, E);
							}
					} else if (
						((h.tag !== 22 && h.tag !== 23) ||
							h.memoizedState === null ||
							h === e) &&
						h.child !== null
					) {
						(h.child.return = h), (h = h.child);
						continue;
					}
					if (h === e) break;
					for (; h.sibling === null; ) {
						if (h.return === null || h.return === e) break e;
						v === h && (v = null), (h = h.return);
					}
					v === h && (v = null), (h.sibling.return = h.return), (h = h.sibling);
				}
			}
			break;
		case 19:
			De(t, e), Be(e), r & 4 && Us(e);
			break;
		case 21:
			break;
		default:
			De(t, e), Be(e);
	}
}
function Be(e) {
	var t = e.flags;
	if (t & 2) {
		try {
			e: {
				for (var n = e.return; n !== null; ) {
					if (Qa(n)) {
						var r = n;
						break e;
					}
					n = n.return;
				}
				throw Error(w(160));
			}
			switch (r.tag) {
				case 5: {
					var l = r.stateNode;
					r.flags & 32 && (Bn(l, ""), (r.flags &= -33));
					var i = As(e);
					Ui(e, i, l);
					break;
				}
				case 3:
				case 4: {
					var o = r.stateNode.containerInfo,
						s = As(e);
					Ai(e, s, o);
					break;
				}
				default:
					throw Error(w(161));
			}
		} catch (u) {
			X(e, e.return, u);
		}
		e.flags &= -3;
	}
	t & 4096 && (e.flags &= -4097);
}
function xf(e, t, n) {
	(T = e), Xa(e);
}
function Xa(e, t, n) {
	for (var r = (e.mode & 1) !== 0; T !== null; ) {
		var l = T,
			i = l.child;
		if (l.tag === 22 && r) {
			var o = l.memoizedState !== null || Nr;
			if (!o) {
				var s = l.alternate,
					u = (s !== null && s.memoizedState !== null) || ce;
				s = Nr;
				var f = ce;
				if (((Nr = o), (ce = u) && !f))
					for (T = l; T !== null; )
						(o = T),
							(u = o.child),
							o.tag === 22 && o.memoizedState !== null
								? Bs(l)
								: u !== null
									? ((u.return = o), (T = u))
									: Bs(l);
				for (; i !== null; ) (T = i), Xa(i), (i = i.sibling);
				(T = l), (Nr = s), (ce = f);
			}
			$s(e);
		} else
			l.subtreeFlags & 8772 && i !== null ? ((i.return = l), (T = i)) : $s(e);
	}
}
function $s(e) {
	for (; T !== null; ) {
		var t = T;
		if (t.flags & 8772) {
			var n = t.alternate;
			try {
				if (t.flags & 8772)
					switch (t.tag) {
						case 0:
						case 11:
						case 15:
							ce || yl(5, t);
							break;
						case 1: {
							var r = t.stateNode;
							if (t.flags & 4 && !ce)
								if (n === null) r.componentDidMount();
								else {
									var l =
										t.elementType === t.type
											? n.memoizedProps
											: Ie(t.type, n.memoizedProps);
									r.componentDidUpdate(
										l,
										n.memoizedState,
										r.__reactInternalSnapshotBeforeUpdate,
									);
								}
							var i = t.updateQueue;
							i !== null && Es(t, i, r);
							break;
						}
						case 3: {
							var o = t.updateQueue;
							if (o !== null) {
								if (((n = null), t.child !== null))
									switch (t.child.tag) {
										case 5:
											n = t.child.stateNode;
											break;
										case 1:
											n = t.child.stateNode;
									}
								Es(t, o, n);
							}
							break;
						}
						case 5: {
							var s = t.stateNode;
							if (n === null && t.flags & 4) {
								n = s;
								var u = t.memoizedProps;
								switch (t.type) {
									case "button":
									case "input":
									case "select":
									case "textarea":
										u.autoFocus && n.focus();
										break;
									case "img":
										u.src && (n.src = u.src);
								}
							}
							break;
						}
						case 6:
							break;
						case 4:
							break;
						case 12:
							break;
						case 13:
							if (t.memoizedState === null) {
								var f = t.alternate;
								if (f !== null) {
									var v = f.memoizedState;
									if (v !== null) {
										var h = v.dehydrated;
										h !== null && Qn(h);
									}
								}
							}
							break;
						case 19:
						case 17:
						case 21:
						case 22:
						case 23:
						case 25:
							break;
						default:
							throw Error(w(163));
					}
				ce || (t.flags & 512 && Mi(t));
			} catch (m) {
				X(t, t.return, m);
			}
		}
		if (t === e) {
			T = null;
			break;
		}
		if (((n = t.sibling), n !== null)) {
			(n.return = t.return), (T = n);
			break;
		}
		T = t.return;
	}
}
function Ws(e) {
	for (; T !== null; ) {
		var t = T;
		if (t === e) {
			T = null;
			break;
		}
		var n = t.sibling;
		if (n !== null) {
			(n.return = t.return), (T = n);
			break;
		}
		T = t.return;
	}
}
function Bs(e) {
	for (; T !== null; ) {
		var t = T;
		try {
			switch (t.tag) {
				case 0:
				case 11:
				case 15: {
					var n = t.return;
					try {
						yl(4, t);
					} catch (u) {
						X(t, n, u);
					}
					break;
				}
				case 1: {
					var r = t.stateNode;
					if (typeof r.componentDidMount == "function") {
						var l = t.return;
						try {
							r.componentDidMount();
						} catch (u) {
							X(t, l, u);
						}
					}
					var i = t.return;
					try {
						Mi(t);
					} catch (u) {
						X(t, i, u);
					}
					break;
				}
				case 5: {
					var o = t.return;
					try {
						Mi(t);
					} catch (u) {
						X(t, o, u);
					}
				}
			}
		} catch (u) {
			X(t, t.return, u);
		}
		if (t === e) {
			T = null;
			break;
		}
		var s = t.sibling;
		if (s !== null) {
			(s.return = t.return), (T = s);
			break;
		}
		T = t.return;
	}
}
var Nf = Math.ceil,
	rl = rt.ReactCurrentDispatcher,
	Po = rt.ReactCurrentOwner,
	ze = rt.ReactCurrentBatchConfig,
	M = 0,
	re = null,
	q = null,
	oe = 0,
	xe = 0,
	en = xt(0),
	te = 0,
	rr = null,
	Ft = 0,
	gl = 0,
	To = 0,
	Un = null,
	ye = null,
	Lo = 0,
	hn = 1 / 0,
	Ge = null,
	ll = !1,
	$i = null,
	vt = null,
	Er = !1,
	ct = null,
	il = 0,
	$n = 0,
	Wi = null,
	Ir = -1,
	Fr = 0;
function he() {
	return M & 6 ? J() : Ir !== -1 ? Ir : (Ir = J());
}
function yt(e) {
	return e.mode & 1
		? M & 2 && oe !== 0
			? oe & -oe
			: of.transition !== null
				? (Fr === 0 && (Fr = Ou()), Fr)
				: ((e = A),
					e !== 0 || ((e = window.event), (e = e === void 0 ? 16 : $u(e.type))),
					e)
		: 1;
}
function Ue(e, t, n, r) {
	if (50 < $n) throw (($n = 0), (Wi = null), Error(w(185)));
	ir(e, n, r),
		(!(M & 2) || e !== re) &&
			(e === re && (!(M & 2) && (gl |= n), te === 4 && ut(e, oe)),
			ke(e, r),
			n === 1 && M === 0 && !(t.mode & 1) && ((hn = J() + 500), hl && Nt()));
}
function ke(e, t) {
	var n = e.callbackNode;
	id(e, t);
	var r = Br(e, e === re ? oe : 0);
	if (r === 0)
		n !== null && Jo(n), (e.callbackNode = null), (e.callbackPriority = 0);
	else if (((t = r & -r), e.callbackPriority !== t)) {
		if ((n != null && Jo(n), t === 1))
			e.tag === 0 ? lf(Vs.bind(null, e)) : ia(Vs.bind(null, e)),
				ef(() => {
					!(M & 6) && Nt();
				}),
				(n = null);
		else {
			switch (Du(r)) {
				case 1:
					n = to;
					break;
				case 4:
					n = zu;
					break;
				case 16:
					n = Wr;
					break;
				case 536870912:
					n = Ru;
					break;
				default:
					n = Wr;
			}
			n = rc(n, Za.bind(null, e));
		}
		(e.callbackPriority = t), (e.callbackNode = n);
	}
}
function Za(e, t) {
	if (((Ir = -1), (Fr = 0), M & 6)) throw Error(w(327));
	var n = e.callbackNode;
	if (sn() && e.callbackNode !== n) return null;
	var r = Br(e, e === re ? oe : 0);
	if (r === 0) return null;
	if (r & 30 || r & e.expiredLanes || t) t = ol(e, r);
	else {
		t = r;
		var l = M;
		M |= 2;
		var i = qa();
		(re !== e || oe !== t) && ((Ge = null), (hn = J() + 500), zt(e, t));
		do
			try {
				_f();
				break;
			} catch (s) {
				Ja(e, s);
			}
		while (1);
		mo(),
			(rl.current = i),
			(M = l),
			q !== null ? (t = 0) : ((re = null), (oe = 0), (t = te));
	}
	if (t !== 0) {
		if (
			(t === 2 && ((l = hi(e)), l !== 0 && ((r = l), (t = Bi(e, l)))), t === 1)
		)
			throw ((n = rr), zt(e, 0), ut(e, r), ke(e, J()), n);
		if (t === 6) ut(e, r);
		else {
			if (
				((l = e.current.alternate),
				!(r & 30) &&
					!Ef(l) &&
					((t = ol(e, r)),
					t === 2 && ((i = hi(e)), i !== 0 && ((r = i), (t = Bi(e, i)))),
					t === 1))
			)
				throw ((n = rr), zt(e, 0), ut(e, r), ke(e, J()), n);
			switch (((e.finishedWork = l), (e.finishedLanes = r), t)) {
				case 0:
				case 1:
					throw Error(w(345));
				case 2:
					jt(e, ye, Ge);
					break;
				case 3:
					if (
						(ut(e, r), (r & 130023424) === r && ((t = Lo + 500 - J()), 10 < t))
					) {
						if (Br(e, 0) !== 0) break;
						if (((l = e.suspendedLanes), (l & r) !== r)) {
							he(), (e.pingedLanes |= e.suspendedLanes & l);
							break;
						}
						e.timeoutHandle = xi(jt.bind(null, e, ye, Ge), t);
						break;
					}
					jt(e, ye, Ge);
					break;
				case 4:
					if ((ut(e, r), (r & 4194240) === r)) break;
					for (t = e.eventTimes, l = -1; 0 < r; ) {
						var o = 31 - Ae(r);
						(i = 1 << o), (o = t[o]), o > l && (l = o), (r &= ~i);
					}
					if (
						((r = l),
						(r = J() - r),
						(r =
							(120 > r
								? 120
								: 480 > r
									? 480
									: 1080 > r
										? 1080
										: 1920 > r
											? 1920
											: 3e3 > r
												? 3e3
												: 4320 > r
													? 4320
													: 1960 * Nf(r / 1960)) - r),
						10 < r)
					) {
						e.timeoutHandle = xi(jt.bind(null, e, ye, Ge), r);
						break;
					}
					jt(e, ye, Ge);
					break;
				case 5:
					jt(e, ye, Ge);
					break;
				default:
					throw Error(w(329));
			}
		}
	}
	return ke(e, J()), e.callbackNode === n ? Za.bind(null, e) : null;
}
function Bi(e, t) {
	var n = Un;
	return (
		e.current.memoizedState.isDehydrated && (zt(e, t).flags |= 256),
		(e = ol(e, t)),
		e !== 2 && ((t = ye), (ye = n), t !== null && Vi(t)),
		e
	);
}
function Vi(e) {
	ye === null ? (ye = e) : ye.push.apply(ye, e);
}
function Ef(e) {
	for (var t = e; ; ) {
		if (t.flags & 16384) {
			var n = t.updateQueue;
			if (n !== null && ((n = n.stores), n !== null))
				for (var r = 0; r < n.length; r++) {
					var l = n[r],
						i = l.getSnapshot;
					l = l.value;
					try {
						if (!$e(i(), l)) return !1;
					} catch {
						return !1;
					}
				}
		}
		if (((n = t.child), t.subtreeFlags & 16384 && n !== null))
			(n.return = t), (t = n);
		else {
			if (t === e) break;
			for (; t.sibling === null; ) {
				if (t.return === null || t.return === e) return !0;
				t = t.return;
			}
			(t.sibling.return = t.return), (t = t.sibling);
		}
	}
	return !0;
}
function ut(e, t) {
	for (
		t &= ~To,
			t &= ~gl,
			e.suspendedLanes |= t,
			e.pingedLanes &= ~t,
			e = e.expirationTimes;
		0 < t;
	) {
		var n = 31 - Ae(t),
			r = 1 << n;
		(e[n] = -1), (t &= ~r);
	}
}
function Vs(e) {
	if (M & 6) throw Error(w(327));
	sn();
	var t = Br(e, 0);
	if (!(t & 1)) return ke(e, J()), null;
	var n = ol(e, t);
	if (e.tag !== 0 && n === 2) {
		var r = hi(e);
		r !== 0 && ((t = r), (n = Bi(e, r)));
	}
	if (n === 1) throw ((n = rr), zt(e, 0), ut(e, t), ke(e, J()), n);
	if (n === 6) throw Error(w(345));
	return (
		(e.finishedWork = e.current.alternate),
		(e.finishedLanes = t),
		jt(e, ye, Ge),
		ke(e, J()),
		null
	);
}
function zo(e, t) {
	var n = M;
	M |= 1;
	try {
		return e(t);
	} finally {
		(M = n), M === 0 && ((hn = J() + 500), hl && Nt());
	}
}
function Mt(e) {
	ct !== null && ct.tag === 0 && !(M & 6) && sn();
	var t = M;
	M |= 1;
	var n = ze.transition,
		r = A;
	try {
		if (((ze.transition = null), (A = 1), e)) return e();
	} finally {
		(A = r), (ze.transition = n), (M = t), !(M & 6) && Nt();
	}
}
function Ro() {
	(xe = en.current), V(en);
}
function zt(e, t) {
	(e.finishedWork = null), (e.finishedLanes = 0);
	var n = e.timeoutHandle;
	if ((n !== -1 && ((e.timeoutHandle = -1), bd(n)), q !== null))
		for (n = q.return; n !== null; ) {
			var r = n;
			switch ((fo(r), r.tag)) {
				case 1:
					(r = r.type.childContextTypes), r != null && Yr();
					break;
				case 3:
					fn(), V(we), V(de), ko();
					break;
				case 5:
					So(r);
					break;
				case 4:
					fn();
					break;
				case 13:
					V(K);
					break;
				case 19:
					V(K);
					break;
				case 10:
					vo(r.type._context);
					break;
				case 22:
				case 23:
					Ro();
			}
			n = n.return;
		}
	if (
		((re = e),
		(q = e = gt(e.current, null)),
		(oe = xe = t),
		(te = 0),
		(rr = null),
		(To = gl = Ft = 0),
		(ye = Un = null),
		Tt !== null)
	) {
		for (t = 0; t < Tt.length; t++)
			if (((n = Tt[t]), (r = n.interleaved), r !== null)) {
				n.interleaved = null;
				var l = r.next,
					i = n.pending;
				if (i !== null) {
					var o = i.next;
					(i.next = l), (r.next = o);
				}
				n.pending = r;
			}
		Tt = null;
	}
	return e;
}
function Ja(e, t) {
	do {
		var n = q;
		try {
			if ((mo(), (Rr.current = nl), tl)) {
				for (var r = Q.memoizedState; r !== null; ) {
					var l = r.queue;
					l !== null && (l.pending = null), (r = r.next);
				}
				tl = !1;
			}
			if (
				((It = 0),
				(ne = ee = Q = null),
				(Mn = !1),
				(er = 0),
				(Po.current = null),
				n === null || n.return === null)
			) {
				(te = 1), (rr = t), (q = null);
				break;
			}
			e: {
				var i = e,
					o = n.return,
					s = n,
					u = t;
				if (
					((t = oe),
					(s.flags |= 32768),
					u !== null && typeof u == "object" && typeof u.then == "function")
				) {
					var f = u,
						v = s,
						h = v.tag;
					if (!(v.mode & 1) && (h === 0 || h === 11 || h === 15)) {
						var m = v.alternate;
						m
							? ((v.updateQueue = m.updateQueue),
								(v.memoizedState = m.memoizedState),
								(v.lanes = m.lanes))
							: ((v.updateQueue = null), (v.memoizedState = null));
					}
					var g = Ls(o);
					if (g !== null) {
						(g.flags &= -257),
							zs(g, o, s, i, t),
							g.mode & 1 && Ts(i, f, t),
							(t = g),
							(u = f);
						var x = t.updateQueue;
						if (x === null) {
							var E = new Set();
							E.add(u), (t.updateQueue = E);
						} else x.add(u);
						break e;
					} else {
						if (!(t & 1)) {
							Ts(i, f, t), Oo();
							break e;
						}
						u = Error(w(426));
					}
				} else if (H && s.mode & 1) {
					var D = Ls(o);
					if (D !== null) {
						!(D.flags & 65536) && (D.flags |= 256),
							zs(D, o, s, i, t),
							po(pn(u, s));
						break e;
					}
				}
				(i = u = pn(u, s)),
					te !== 4 && (te = 2),
					Un === null ? (Un = [i]) : Un.push(i),
					(i = o);
				do {
					switch (i.tag) {
						case 3: {
							(i.flags |= 65536), (t &= -t), (i.lanes |= t);
							var p = Da(i, u, t);
							Ns(i, p);
							break e;
						}
						case 1: {
							s = u;
							var a = i.type,
								d = i.stateNode;
							if (
								!(i.flags & 128) &&
								(typeof a.getDerivedStateFromError == "function" ||
									(d !== null &&
										typeof d.componentDidCatch == "function" &&
										(vt === null || !vt.has(d))))
							) {
								(i.flags |= 65536), (t &= -t), (i.lanes |= t);
								var y = Ia(i, s, t);
								Ns(i, y);
								break e;
							}
						}
					}
					i = i.return;
				} while (i !== null);
			}
			ec(n);
		} catch (N) {
			(t = N), q === n && n !== null && (q = n = n.return);
			continue;
		}
		break;
	} while (1);
}
function qa() {
	var e = rl.current;
	return (rl.current = nl), e === null ? nl : e;
}
function Oo() {
	(te === 0 || te === 3 || te === 2) && (te = 4),
		re === null || (!(Ft & 268435455) && !(gl & 268435455)) || ut(re, oe);
}
function ol(e, t) {
	var n = M;
	M |= 2;
	var r = qa();
	(re !== e || oe !== t) && ((Ge = null), zt(e, t));
	do
		try {
			Cf();
			break;
		} catch (l) {
			Ja(e, l);
		}
	while (1);
	if ((mo(), (M = n), (rl.current = r), q !== null)) throw Error(w(261));
	return (re = null), (oe = 0), te;
}
function Cf() {
	for (; q !== null; ) ba(q);
}
function _f() {
	for (; q !== null && !Zc(); ) ba(q);
}
function ba(e) {
	var t = nc(e.alternate, e, xe);
	(e.memoizedProps = e.pendingProps),
		t === null ? ec(e) : (q = t),
		(Po.current = null);
}
function ec(e) {
	var t = e;
	do {
		var n = t.alternate;
		if (((e = t.return), t.flags & 32768)) {
			if (((n = wf(n, t)), n !== null)) {
				(n.flags &= 32767), (q = n);
				return;
			}
			if (e !== null)
				(e.flags |= 32768), (e.subtreeFlags = 0), (e.deletions = null);
			else {
				(te = 6), (q = null);
				return;
			}
		} else if (((n = gf(n, t, xe)), n !== null)) {
			q = n;
			return;
		}
		if (((t = t.sibling), t !== null)) {
			q = t;
			return;
		}
		q = t = e;
	} while (t !== null);
	te === 0 && (te = 5);
}
function jt(e, t, n) {
	var r = A,
		l = ze.transition;
	try {
		(ze.transition = null), (A = 1), jf(e, t, n, r);
	} finally {
		(ze.transition = l), (A = r);
	}
	return null;
}
function jf(e, t, n, r) {
	do sn();
	while (ct !== null);
	if (M & 6) throw Error(w(327));
	n = e.finishedWork;
	var l = e.finishedLanes;
	if (n === null) return null;
	if (((e.finishedWork = null), (e.finishedLanes = 0), n === e.current))
		throw Error(w(177));
	(e.callbackNode = null), (e.callbackPriority = 0);
	var i = n.lanes | n.childLanes;
	if (
		(od(e, i),
		e === re && ((q = re = null), (oe = 0)),
		(!(n.subtreeFlags & 2064) && !(n.flags & 2064)) ||
			Er ||
			((Er = !0), rc(Wr, () => (sn(), null))),
		(i = (n.flags & 15990) !== 0),
		n.subtreeFlags & 15990 || i)
	) {
		(i = ze.transition), (ze.transition = null);
		var o = A;
		A = 1;
		var s = M;
		(M |= 4),
			(Po.current = null),
			kf(e, n),
			Ga(n, e),
			Qd(Si),
			(Vr = !!wi),
			(Si = wi = null),
			(e.current = n),
			xf(n),
			Jc(),
			(M = s),
			(A = o),
			(ze.transition = i);
	} else e.current = n;
	if (
		(Er && ((Er = !1), (ct = e), (il = l)),
		(i = e.pendingLanes),
		i === 0 && (vt = null),
		ed(n.stateNode),
		ke(e, J()),
		t !== null)
	)
		for (r = e.onRecoverableError, n = 0; n < t.length; n++)
			(l = t[n]), r(l.value, { componentStack: l.stack, digest: l.digest });
	if (ll) throw ((ll = !1), (e = $i), ($i = null), e);
	return (
		il & 1 && e.tag !== 0 && sn(),
		(i = e.pendingLanes),
		i & 1 ? (e === Wi ? $n++ : (($n = 0), (Wi = e))) : ($n = 0),
		Nt(),
		null
	);
}
function sn() {
	if (ct !== null) {
		var e = Du(il),
			t = ze.transition,
			n = A;
		try {
			if (((ze.transition = null), (A = 16 > e ? 16 : e), ct === null))
				var r = !1;
			else {
				if (((e = ct), (ct = null), (il = 0), M & 6)) throw Error(w(331));
				var l = M;
				for (M |= 4, T = e.current; T !== null; ) {
					var i = T,
						o = i.child;
					if (T.flags & 16) {
						var s = i.deletions;
						if (s !== null) {
							for (var u = 0; u < s.length; u++) {
								var f = s[u];
								for (T = f; T !== null; ) {
									var v = T;
									switch (v.tag) {
										case 0:
										case 11:
										case 15:
											An(8, v, i);
									}
									var h = v.child;
									if (h !== null) (h.return = v), (T = h);
									else
										for (; T !== null; ) {
											v = T;
											var m = v.sibling,
												g = v.return;
											if ((Ka(v), v === f)) {
												T = null;
												break;
											}
											if (m !== null) {
												(m.return = g), (T = m);
												break;
											}
											T = g;
										}
								}
							}
							var x = i.alternate;
							if (x !== null) {
								var E = x.child;
								if (E !== null) {
									x.child = null;
									do {
										var D = E.sibling;
										(E.sibling = null), (E = D);
									} while (E !== null);
								}
							}
							T = i;
						}
					}
					if (i.subtreeFlags & 2064 && o !== null) (o.return = i), (T = o);
					else
						for (; T !== null; ) {
							if (((i = T), i.flags & 2048))
								switch (i.tag) {
									case 0:
									case 11:
									case 15:
										An(9, i, i.return);
								}
							var p = i.sibling;
							if (p !== null) {
								(p.return = i.return), (T = p);
								break;
							}
							T = i.return;
						}
				}
				var a = e.current;
				for (T = a; T !== null; ) {
					o = T;
					var d = o.child;
					if (o.subtreeFlags & 2064 && d !== null) (d.return = o), (T = d);
					else
						for (o = a; T !== null; ) {
							if (((s = T), s.flags & 2048))
								try {
									switch (s.tag) {
										case 0:
										case 11:
										case 15:
											yl(9, s);
									}
								} catch (N) {
									X(s, s.return, N);
								}
							if (s === o) {
								T = null;
								break;
							}
							var y = s.sibling;
							if (y !== null) {
								(y.return = s.return), (T = y);
								break;
							}
							T = s.return;
						}
				}
				if (
					((M = l), Nt(), Ke && typeof Ke.onPostCommitFiberRoot == "function")
				)
					try {
						Ke.onPostCommitFiberRoot(al, e);
					} catch {}
				r = !0;
			}
			return r;
		} finally {
			(A = n), (ze.transition = t);
		}
	}
	return !1;
}
function Hs(e, t, n) {
	(t = pn(n, t)),
		(t = Da(e, t, 1)),
		(e = mt(e, t, 1)),
		(t = he()),
		e !== null && (ir(e, 1, t), ke(e, t));
}
function X(e, t, n) {
	if (e.tag === 3) Hs(e, e, n);
	else
		for (; t !== null; ) {
			if (t.tag === 3) {
				Hs(t, e, n);
				break;
			} else if (t.tag === 1) {
				var r = t.stateNode;
				if (
					typeof t.type.getDerivedStateFromError == "function" ||
					(typeof r.componentDidCatch == "function" &&
						(vt === null || !vt.has(r)))
				) {
					(e = pn(n, e)),
						(e = Ia(t, e, 1)),
						(t = mt(t, e, 1)),
						(e = he()),
						t !== null && (ir(t, 1, e), ke(t, e));
					break;
				}
			}
			t = t.return;
		}
}
function Pf(e, t, n) {
	var r = e.pingCache;
	r !== null && r.delete(t),
		(t = he()),
		(e.pingedLanes |= e.suspendedLanes & n),
		re === e &&
			(oe & n) === n &&
			(te === 4 || (te === 3 && (oe & 130023424) === oe && 500 > J() - Lo)
				? zt(e, 0)
				: (To |= n)),
		ke(e, t);
}
function tc(e, t) {
	t === 0 &&
		(e.mode & 1
			? ((t = hr), (hr <<= 1), !(hr & 130023424) && (hr = 4194304))
			: (t = 1));
	var n = he();
	(e = tt(e, t)), e !== null && (ir(e, t, n), ke(e, n));
}
function Tf(e) {
	var t = e.memoizedState,
		n = 0;
	t !== null && (n = t.retryLane), tc(e, n);
}
function Lf(e, t) {
	var n = 0;
	switch (e.tag) {
		case 13: {
			var r = e.stateNode,
				l = e.memoizedState;
			l !== null && (n = l.retryLane);
			break;
		}
		case 19:
			r = e.stateNode;
			break;
		default:
			throw Error(w(314));
	}
	r !== null && r.delete(t), tc(e, n);
}
var nc;
nc = (e, t, n) => {
	if (e !== null)
		if (e.memoizedProps !== t.pendingProps || we.current) ge = !0;
		else {
			if (!(e.lanes & n) && !(t.flags & 128)) return (ge = !1), yf(e, t, n);
			ge = !!(e.flags & 131072);
		}
	else (ge = !1), H && t.flags & 1048576 && oa(t, Zr, t.index);
	switch (((t.lanes = 0), t.tag)) {
		case 2: {
			var r = t.type;
			Dr(e, t), (e = t.pendingProps);
			var l = an(t, de.current);
			on(t, n), (l = No(null, t, r, e, l, n));
			var i = Eo();
			return (
				(t.flags |= 1),
				typeof l == "object" &&
				l !== null &&
				typeof l.render == "function" &&
				l.$$typeof === void 0
					? ((t.tag = 1),
						(t.memoizedState = null),
						(t.updateQueue = null),
						Se(r) ? ((i = !0), Gr(t)) : (i = !1),
						(t.memoizedState =
							l.state !== null && l.state !== void 0 ? l.state : null),
						go(t),
						(l.updater = vl),
						(t.stateNode = l),
						(l._reactInternals = t),
						Ti(t, r, e, n),
						(t = Ri(null, t, r, !0, i, n)))
					: ((t.tag = 0), H && i && co(t), pe(null, t, l, n), (t = t.child)),
				t
			);
		}
		case 16:
			r = t.elementType;
			e: {
				switch (
					(Dr(e, t),
					(e = t.pendingProps),
					(l = r._init),
					(r = l(r._payload)),
					(t.type = r),
					(l = t.tag = Rf(r)),
					(e = Ie(r, e)),
					l)
				) {
					case 0:
						t = zi(null, t, r, e, n);
						break e;
					case 1:
						t = Ds(null, t, r, e, n);
						break e;
					case 11:
						t = Rs(null, t, r, e, n);
						break e;
					case 14:
						t = Os(null, t, r, Ie(r.type, e), n);
						break e;
				}
				throw Error(w(306, r, ""));
			}
			return t;
		case 0:
			return (
				(r = t.type),
				(l = t.pendingProps),
				(l = t.elementType === r ? l : Ie(r, l)),
				zi(e, t, r, l, n)
			);
		case 1:
			return (
				(r = t.type),
				(l = t.pendingProps),
				(l = t.elementType === r ? l : Ie(r, l)),
				Ds(e, t, r, l, n)
			);
		case 3:
			e: {
				if ((Ua(t), e === null)) throw Error(w(387));
				(r = t.pendingProps),
					(i = t.memoizedState),
					(l = i.element),
					fa(e, t),
					br(t, r, null, n);
				var o = t.memoizedState;
				if (((r = o.element), i.isDehydrated))
					if (
						((i = {
							element: r,
							isDehydrated: !1,
							cache: o.cache,
							pendingSuspenseBoundaries: o.pendingSuspenseBoundaries,
							transitions: o.transitions,
						}),
						(t.updateQueue.baseState = i),
						(t.memoizedState = i),
						t.flags & 256)
					) {
						(l = pn(Error(w(423)), t)), (t = Is(e, t, r, n, l));
						break e;
					} else if (r !== l) {
						(l = pn(Error(w(424)), t)), (t = Is(e, t, r, n, l));
						break e;
					} else
						for (
							Ne = ht(t.stateNode.containerInfo.firstChild),
								Ee = t,
								H = !0,
								Me = null,
								n = ca(t, null, r, n),
								t.child = n;
							n;
						)
							(n.flags = (n.flags & -3) | 4096), (n = n.sibling);
				else {
					if ((cn(), r === l)) {
						t = nt(e, t, n);
						break e;
					}
					pe(e, t, r, n);
				}
				t = t.child;
			}
			return t;
		case 5:
			return (
				pa(t),
				e === null && _i(t),
				(r = t.type),
				(l = t.pendingProps),
				(i = e !== null ? e.memoizedProps : null),
				(o = l.children),
				ki(r, l) ? (o = null) : i !== null && ki(r, i) && (t.flags |= 32),
				Aa(e, t),
				pe(e, t, o, n),
				t.child
			);
		case 6:
			return e === null && _i(t), null;
		case 13:
			return $a(e, t, n);
		case 4:
			return (
				wo(t, t.stateNode.containerInfo),
				(r = t.pendingProps),
				e === null ? (t.child = dn(t, null, r, n)) : pe(e, t, r, n),
				t.child
			);
		case 11:
			return (
				(r = t.type),
				(l = t.pendingProps),
				(l = t.elementType === r ? l : Ie(r, l)),
				Rs(e, t, r, l, n)
			);
		case 7:
			return pe(e, t, t.pendingProps, n), t.child;
		case 8:
			return pe(e, t, t.pendingProps.children, n), t.child;
		case 12:
			return pe(e, t, t.pendingProps.children, n), t.child;
		case 10:
			e: {
				if (
					((r = t.type._context),
					(l = t.pendingProps),
					(i = t.memoizedProps),
					(o = l.value),
					W(Jr, r._currentValue),
					(r._currentValue = o),
					i !== null)
				)
					if ($e(i.value, o)) {
						if (i.children === l.children && !we.current) {
							t = nt(e, t, n);
							break e;
						}
					} else
						for (i = t.child, i !== null && (i.return = t); i !== null; ) {
							var s = i.dependencies;
							if (s !== null) {
								o = i.child;
								for (var u = s.firstContext; u !== null; ) {
									if (u.context === r) {
										if (i.tag === 1) {
											(u = qe(-1, n & -n)), (u.tag = 2);
											var f = i.updateQueue;
											if (f !== null) {
												f = f.shared;
												var v = f.pending;
												v === null
													? (u.next = u)
													: ((u.next = v.next), (v.next = u)),
													(f.pending = u);
											}
										}
										(i.lanes |= n),
											(u = i.alternate),
											u !== null && (u.lanes |= n),
											ji(i.return, n, t),
											(s.lanes |= n);
										break;
									}
									u = u.next;
								}
							} else if (i.tag === 10) o = i.type === t.type ? null : i.child;
							else if (i.tag === 18) {
								if (((o = i.return), o === null)) throw Error(w(341));
								(o.lanes |= n),
									(s = o.alternate),
									s !== null && (s.lanes |= n),
									ji(o, n, t),
									(o = i.sibling);
							} else o = i.child;
							if (o !== null) o.return = i;
							else
								for (o = i; o !== null; ) {
									if (o === t) {
										o = null;
										break;
									}
									if (((i = o.sibling), i !== null)) {
										(i.return = o.return), (o = i);
										break;
									}
									o = o.return;
								}
							i = o;
						}
				pe(e, t, l.children, n), (t = t.child);
			}
			return t;
		case 9:
			return (
				(l = t.type),
				(r = t.pendingProps.children),
				on(t, n),
				(l = Re(l)),
				(r = r(l)),
				(t.flags |= 1),
				pe(e, t, r, n),
				t.child
			);
		case 14:
			return (
				(r = t.type),
				(l = Ie(r, t.pendingProps)),
				(l = Ie(r.type, l)),
				Os(e, t, r, l, n)
			);
		case 15:
			return Fa(e, t, t.type, t.pendingProps, n);
		case 17:
			return (
				(r = t.type),
				(l = t.pendingProps),
				(l = t.elementType === r ? l : Ie(r, l)),
				Dr(e, t),
				(t.tag = 1),
				Se(r) ? ((e = !0), Gr(t)) : (e = !1),
				on(t, n),
				Oa(t, r, l),
				Ti(t, r, l, n),
				Ri(null, t, r, !0, e, n)
			);
		case 19:
			return Wa(e, t, n);
		case 22:
			return Ma(e, t, n);
	}
	throw Error(w(156, t.tag));
};
function rc(e, t) {
	return Lu(e, t);
}
function zf(e, t, n, r) {
	(this.tag = e),
		(this.key = n),
		(this.sibling =
			this.child =
			this.return =
			this.stateNode =
			this.type =
			this.elementType =
				null),
		(this.index = 0),
		(this.ref = null),
		(this.pendingProps = t),
		(this.dependencies =
			this.memoizedState =
			this.updateQueue =
			this.memoizedProps =
				null),
		(this.mode = r),
		(this.subtreeFlags = this.flags = 0),
		(this.deletions = null),
		(this.childLanes = this.lanes = 0),
		(this.alternate = null);
}
function Le(e, t, n, r) {
	return new zf(e, t, n, r);
}
function Do(e) {
	return (e = e.prototype), !(!e || !e.isReactComponent);
}
function Rf(e) {
	if (typeof e == "function") return Do(e) ? 1 : 0;
	if (e != null) {
		if (((e = e.$$typeof), e === qi)) return 11;
		if (e === bi) return 14;
	}
	return 2;
}
function gt(e, t) {
	var n = e.alternate;
	return (
		n === null
			? ((n = Le(e.tag, t, e.key, e.mode)),
				(n.elementType = e.elementType),
				(n.type = e.type),
				(n.stateNode = e.stateNode),
				(n.alternate = e),
				(e.alternate = n))
			: ((n.pendingProps = t),
				(n.type = e.type),
				(n.flags = 0),
				(n.subtreeFlags = 0),
				(n.deletions = null)),
		(n.flags = e.flags & 14680064),
		(n.childLanes = e.childLanes),
		(n.lanes = e.lanes),
		(n.child = e.child),
		(n.memoizedProps = e.memoizedProps),
		(n.memoizedState = e.memoizedState),
		(n.updateQueue = e.updateQueue),
		(t = e.dependencies),
		(n.dependencies =
			t === null ? null : { lanes: t.lanes, firstContext: t.firstContext }),
		(n.sibling = e.sibling),
		(n.index = e.index),
		(n.ref = e.ref),
		n
	);
}
function Mr(e, t, n, r, l, i) {
	var o = 2;
	if (((r = e), typeof e == "function")) Do(e) && (o = 1);
	else if (typeof e == "string") o = 5;
	else
		e: switch (e) {
			case Ht:
				return Rt(n.children, l, i, t);
			case Ji:
				(o = 8), (l |= 8);
				break;
			case bl:
				return (
					(e = Le(12, n, t, l | 2)), (e.elementType = bl), (e.lanes = i), e
				);
			case ei:
				return (e = Le(13, n, t, l)), (e.elementType = ei), (e.lanes = i), e;
			case ti:
				return (e = Le(19, n, t, l)), (e.elementType = ti), (e.lanes = i), e;
			case pu:
				return wl(n, l, i, t);
			default:
				if (typeof e == "object" && e !== null)
					switch (e.$$typeof) {
						case du:
							o = 10;
							break e;
						case fu:
							o = 9;
							break e;
						case qi:
							o = 11;
							break e;
						case bi:
							o = 14;
							break e;
						case it:
							(o = 16), (r = null);
							break e;
					}
				throw Error(w(130, e == null ? e : typeof e, ""));
		}
	return (
		(t = Le(o, n, t, l)), (t.elementType = e), (t.type = r), (t.lanes = i), t
	);
}
function Rt(e, t, n, r) {
	return (e = Le(7, e, r, t)), (e.lanes = n), e;
}
function wl(e, t, n, r) {
	return (
		(e = Le(22, e, r, t)),
		(e.elementType = pu),
		(e.lanes = n),
		(e.stateNode = { isHidden: !1 }),
		e
	);
}
function Gl(e, t, n) {
	return (e = Le(6, e, null, t)), (e.lanes = n), e;
}
function Xl(e, t, n) {
	return (
		(t = Le(4, e.children !== null ? e.children : [], e.key, t)),
		(t.lanes = n),
		(t.stateNode = {
			containerInfo: e.containerInfo,
			pendingChildren: null,
			implementation: e.implementation,
		}),
		t
	);
}
function Of(e, t, n, r, l) {
	(this.tag = t),
		(this.containerInfo = e),
		(this.finishedWork =
			this.pingCache =
			this.current =
			this.pendingChildren =
				null),
		(this.timeoutHandle = -1),
		(this.callbackNode = this.pendingContext = this.context = null),
		(this.callbackPriority = 0),
		(this.eventTimes = Tl(0)),
		(this.expirationTimes = Tl(-1)),
		(this.entangledLanes =
			this.finishedLanes =
			this.mutableReadLanes =
			this.expiredLanes =
			this.pingedLanes =
			this.suspendedLanes =
			this.pendingLanes =
				0),
		(this.entanglements = Tl(0)),
		(this.identifierPrefix = r),
		(this.onRecoverableError = l),
		(this.mutableSourceEagerHydrationData = null);
}
function Io(e, t, n, r, l, i, o, s, u) {
	return (
		(e = new Of(e, t, n, s, u)),
		t === 1 ? ((t = 1), i === !0 && (t |= 8)) : (t = 0),
		(i = Le(3, null, null, t)),
		(e.current = i),
		(i.stateNode = e),
		(i.memoizedState = {
			element: r,
			isDehydrated: n,
			cache: null,
			transitions: null,
			pendingSuspenseBoundaries: null,
		}),
		go(i),
		e
	);
}
function Df(e, t, n) {
	var r = 3 < arguments.length && arguments[3] !== void 0 ? arguments[3] : null;
	return {
		$$typeof: Vt,
		key: r == null ? null : "" + r,
		children: e,
		containerInfo: t,
		implementation: n,
	};
}
function lc(e) {
	if (!e) return St;
	e = e._reactInternals;
	e: {
		if (Ut(e) !== e || e.tag !== 1) throw Error(w(170));
		var t = e;
		do {
			switch (t.tag) {
				case 3:
					t = t.stateNode.context;
					break e;
				case 1:
					if (Se(t.type)) {
						t = t.stateNode.__reactInternalMemoizedMergedChildContext;
						break e;
					}
			}
			t = t.return;
		} while (t !== null);
		throw Error(w(171));
	}
	if (e.tag === 1) {
		var n = e.type;
		if (Se(n)) return la(e, n, t);
	}
	return t;
}
function ic(e, t, n, r, l, i, o, s, u) {
	return (
		(e = Io(n, r, !0, e, l, i, o, s, u)),
		(e.context = lc(null)),
		(n = e.current),
		(r = he()),
		(l = yt(n)),
		(i = qe(r, l)),
		(i.callback = t ?? null),
		mt(n, i, l),
		(e.current.lanes = l),
		ir(e, l, r),
		ke(e, r),
		e
	);
}
function Sl(e, t, n, r) {
	var l = t.current,
		i = he(),
		o = yt(l);
	return (
		(n = lc(n)),
		t.context === null ? (t.context = n) : (t.pendingContext = n),
		(t = qe(i, o)),
		(t.payload = { element: e }),
		(r = r === void 0 ? null : r),
		r !== null && (t.callback = r),
		(e = mt(l, t, o)),
		e !== null && (Ue(e, l, o, i), zr(e, l, o)),
		o
	);
}
function sl(e) {
	if (((e = e.current), !e.child)) return null;
	switch (e.child.tag) {
		case 5:
			return e.child.stateNode;
		default:
			return e.child.stateNode;
	}
}
function Ks(e, t) {
	if (((e = e.memoizedState), e !== null && e.dehydrated !== null)) {
		var n = e.retryLane;
		e.retryLane = n !== 0 && n < t ? n : t;
	}
}
function Fo(e, t) {
	Ks(e, t), (e = e.alternate) && Ks(e, t);
}
function If() {
	return null;
}
var oc =
	typeof reportError == "function"
		? reportError
		: (e) => {
				console.error(e);
			};
function Mo(e) {
	this._internalRoot = e;
}
kl.prototype.render = Mo.prototype.render = function (e) {
	var t = this._internalRoot;
	if (t === null) throw Error(w(409));
	Sl(e, t, null, null);
};
kl.prototype.unmount = Mo.prototype.unmount = function () {
	var e = this._internalRoot;
	if (e !== null) {
		this._internalRoot = null;
		var t = e.containerInfo;
		Mt(() => {
			Sl(null, e, null, null);
		}),
			(t[et] = null);
	}
};
function kl(e) {
	this._internalRoot = e;
}
kl.prototype.unstable_scheduleHydration = (e) => {
	if (e) {
		var t = Mu();
		e = { blockedOn: null, target: e, priority: t };
		for (var n = 0; n < st.length && t !== 0 && t < st[n].priority; n++);
		st.splice(n, 0, e), n === 0 && Uu(e);
	}
};
function Ao(e) {
	return !(!e || (e.nodeType !== 1 && e.nodeType !== 9 && e.nodeType !== 11));
}
function xl(e) {
	return !(
		!e ||
		(e.nodeType !== 1 &&
			e.nodeType !== 9 &&
			e.nodeType !== 11 &&
			(e.nodeType !== 8 || e.nodeValue !== " react-mount-point-unstable "))
	);
}
function Qs() {}
function Ff(e, t, n, r, l) {
	if (l) {
		if (typeof r == "function") {
			var i = r;
			r = () => {
				var f = sl(o);
				i.call(f);
			};
		}
		var o = ic(t, r, e, 0, null, !1, !1, "", Qs);
		return (
			(e._reactRootContainer = o),
			(e[et] = o.current),
			Xn(e.nodeType === 8 ? e.parentNode : e),
			Mt(),
			o
		);
	}
	for (; (l = e.lastChild); ) e.removeChild(l);
	if (typeof r == "function") {
		var s = r;
		r = () => {
			var f = sl(u);
			s.call(f);
		};
	}
	var u = Io(e, 0, !1, null, null, !1, !1, "", Qs);
	return (
		(e._reactRootContainer = u),
		(e[et] = u.current),
		Xn(e.nodeType === 8 ? e.parentNode : e),
		Mt(() => {
			Sl(t, u, n, r);
		}),
		u
	);
}
function Nl(e, t, n, r, l) {
	var i = n._reactRootContainer;
	if (i) {
		var o = i;
		if (typeof l == "function") {
			var s = l;
			l = () => {
				var u = sl(o);
				s.call(u);
			};
		}
		Sl(t, o, e, l);
	} else o = Ff(n, t, e, l, r);
	return sl(o);
}
Iu = (e) => {
	switch (e.tag) {
		case 3: {
			var t = e.stateNode;
			if (t.current.memoizedState.isDehydrated) {
				var n = Ln(t.pendingLanes);
				n !== 0 &&
					(no(t, n | 1), ke(t, J()), !(M & 6) && ((hn = J() + 500), Nt()));
			}
			break;
		}
		case 13:
			Mt(() => {
				var r = tt(e, 1);
				if (r !== null) {
					var l = he();
					Ue(r, e, 1, l);
				}
			}),
				Fo(e, 1);
	}
};
ro = (e) => {
	if (e.tag === 13) {
		var t = tt(e, 134217728);
		if (t !== null) {
			var n = he();
			Ue(t, e, 134217728, n);
		}
		Fo(e, 134217728);
	}
};
Fu = (e) => {
	if (e.tag === 13) {
		var t = yt(e),
			n = tt(e, t);
		if (n !== null) {
			var r = he();
			Ue(n, e, t, r);
		}
		Fo(e, t);
	}
};
Mu = () => A;
Au = (e, t) => {
	var n = A;
	try {
		return (A = e), t();
	} finally {
		A = n;
	}
};
di = (e, t, n) => {
	switch (t) {
		case "input":
			if ((li(e, n), (t = n.name), n.type === "radio" && t != null)) {
				for (n = e; n.parentNode; ) n = n.parentNode;
				for (
					n = n.querySelectorAll(
						"input[name=" + JSON.stringify("" + t) + '][type="radio"]',
					),
						t = 0;
					t < n.length;
					t++
				) {
					var r = n[t];
					if (r !== e && r.form === e.form) {
						var l = pl(r);
						if (!l) throw Error(w(90));
						mu(r), li(r, l);
					}
				}
			}
			break;
		case "textarea":
			yu(e, n);
			break;
		case "select":
			(t = n.value), t != null && tn(e, !!n.multiple, t, !1);
	}
};
Eu = zo;
Cu = Mt;
var Mf = { usingClientEntryPoint: !1, Events: [sr, Gt, pl, xu, Nu, zo] },
	jn = {
		findFiberByHostInstance: Pt,
		bundleType: 0,
		version: "18.3.1",
		rendererPackageName: "react-dom",
	},
	Af = {
		bundleType: jn.bundleType,
		version: jn.version,
		rendererPackageName: jn.rendererPackageName,
		rendererConfig: jn.rendererConfig,
		overrideHookState: null,
		overrideHookStateDeletePath: null,
		overrideHookStateRenamePath: null,
		overrideProps: null,
		overridePropsDeletePath: null,
		overridePropsRenamePath: null,
		setErrorHandler: null,
		setSuspenseHandler: null,
		scheduleUpdate: null,
		currentDispatcherRef: rt.ReactCurrentDispatcher,
		findHostInstanceByFiber: (e) => (
			(e = Pu(e)), e === null ? null : e.stateNode
		),
		findFiberByHostInstance: jn.findFiberByHostInstance || If,
		findHostInstancesForRefresh: null,
		scheduleRefresh: null,
		scheduleRoot: null,
		setRefreshHandler: null,
		getCurrentFiber: null,
		reconcilerVersion: "18.3.1-next-f1338f8080-20240426",
	};
if (typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u") {
	var Cr = __REACT_DEVTOOLS_GLOBAL_HOOK__;
	if (!Cr.isDisabled && Cr.supportsFiber)
		try {
			(al = Cr.inject(Af)), (Ke = Cr);
		} catch {}
}
_e.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = Mf;
_e.createPortal = function (e, t) {
	var n = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null;
	if (!Ao(t)) throw Error(w(200));
	return Df(e, t, null, n);
};
_e.createRoot = (e, t) => {
	if (!Ao(e)) throw Error(w(299));
	var n = !1,
		r = "",
		l = oc;
	return (
		t != null &&
			(t.unstable_strictMode === !0 && (n = !0),
			t.identifierPrefix !== void 0 && (r = t.identifierPrefix),
			t.onRecoverableError !== void 0 && (l = t.onRecoverableError)),
		(t = Io(e, 1, !1, null, null, n, !1, r, l)),
		(e[et] = t.current),
		Xn(e.nodeType === 8 ? e.parentNode : e),
		new Mo(t)
	);
};
_e.findDOMNode = (e) => {
	if (e == null) return null;
	if (e.nodeType === 1) return e;
	var t = e._reactInternals;
	if (t === void 0)
		throw typeof e.render == "function"
			? Error(w(188))
			: ((e = Object.keys(e).join(",")), Error(w(268, e)));
	return (e = Pu(t)), (e = e === null ? null : e.stateNode), e;
};
_e.flushSync = (e) => Mt(e);
_e.hydrate = (e, t, n) => {
	if (!xl(t)) throw Error(w(200));
	return Nl(null, e, t, !0, n);
};
_e.hydrateRoot = (e, t, n) => {
	if (!Ao(e)) throw Error(w(405));
	var r = (n != null && n.hydratedSources) || null,
		l = !1,
		i = "",
		o = oc;
	if (
		(n != null &&
			(n.unstable_strictMode === !0 && (l = !0),
			n.identifierPrefix !== void 0 && (i = n.identifierPrefix),
			n.onRecoverableError !== void 0 && (o = n.onRecoverableError)),
		(t = ic(t, null, e, 1, n ?? null, l, !1, i, o)),
		(e[et] = t.current),
		Xn(e),
		r)
	)
		for (e = 0; e < r.length; e++)
			(n = r[e]),
				(l = n._getVersion),
				(l = l(n._source)),
				t.mutableSourceEagerHydrationData == null
					? (t.mutableSourceEagerHydrationData = [n, l])
					: t.mutableSourceEagerHydrationData.push(n, l);
	return new kl(t);
};
_e.render = (e, t, n) => {
	if (!xl(t)) throw Error(w(200));
	return Nl(null, e, t, !1, n);
};
_e.unmountComponentAtNode = (e) => {
	if (!xl(e)) throw Error(w(40));
	return e._reactRootContainer
		? (Mt(() => {
				Nl(null, null, e, !1, () => {
					(e._reactRootContainer = null), (e[et] = null);
				});
			}),
			!0)
		: !1;
};
_e.unstable_batchedUpdates = zo;
_e.unstable_renderSubtreeIntoContainer = (e, t, n, r) => {
	if (!xl(n)) throw Error(w(200));
	if (e == null || e._reactInternals === void 0) throw Error(w(38));
	return Nl(e, t, n, !1, r);
};
_e.version = "18.3.1-next-f1338f8080-20240426";
function sc() {
	if (
		!(
			typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" ||
			typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"
		)
	)
		try {
			__REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(sc);
		} catch (e) {
			console.error(e);
		}
}
sc(), (su.exports = _e);
var Uf = su.exports,
	Ys = Uf;
(Jl.createRoot = Ys.createRoot), (Jl.hydrateRoot = Ys.hydrateRoot);
var $f = {
	xmlns: "http://www.w3.org/2000/svg",
	width: 24,
	height: 24,
	viewBox: "0 0 24 24",
	fill: "none",
	stroke: "currentColor",
	strokeWidth: 2,
	strokeLinecap: "round",
	strokeLinejoin: "round",
};
const Wf = (e) => e.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase(),
	Bf = (e, t) => {
		const n = R.forwardRef(
			(
				{
					color: r = "currentColor",
					size: l = 24,
					strokeWidth: i = 2,
					absoluteStrokeWidth: o,
					children: s,
					...u
				},
				f,
			) =>
				R.createElement(
					"svg",
					{
						ref: f,
						...$f,
						width: l,
						height: l,
						stroke: r,
						strokeWidth: o ? (Number(i) * 24) / Number(l) : i,
						className: `lucide lucide-${Wf(e)}`,
						...u,
					},
					[
						...t.map(([v, h]) => R.createElement(v, h)),
						...((Array.isArray(s) ? s : [s]) || []),
					],
				),
		);
		return (n.displayName = `${e}`), n;
	};
var gn = Bf;
const uc = gn("Layers", [
		["polygon", { points: "12 2 2 7 12 12 22 7 12 2", key: "1b0ttc" }],
		["polyline", { points: "2 17 12 22 22 17", key: "imjtdl" }],
		["polyline", { points: "2 12 12 17 22 12", key: "5dexcv" }],
	]),
	Vf = gn("Lightbulb", [
		[
			"path",
			{
				d: "M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5",
				key: "1gvzjb",
			},
		],
		["path", { d: "M9 18h6", key: "x1upvd" }],
		["path", { d: "M10 22h4", key: "ceow96" }],
	]),
	Hf = gn("Loader2", [
		["path", { d: "M21 12a9 9 0 1 1-6.219-8.56", key: "13zald" }],
	]),
	Kf = gn("Play", [
		["polygon", { points: "5 3 19 12 5 21 5 3", key: "191637" }],
	]),
	Qf = gn("Settings", [
		[
			"path",
			{
				d: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z",
				key: "1qme2f",
			},
		],
		["circle", { cx: "12", cy: "12", r: "3", key: "1v7zrd" }],
	]),
	Yf = gn("Terminal", [
		["polyline", { points: "4 17 10 11 4 5", key: "akl6gq" }],
		["line", { x1: "12", x2: "20", y1: "19", y2: "19", key: "q2wloq" }],
	]),
	ac = {}.VITE_API_URL ?? "http://localhost:8000";
async function b(e, t) {
	const n = await fetch(`${ac}${e}`, {
		headers: { "Content-Type": "application/json" },
		...t,
	});
	if (!n.ok) throw new Error(`API ${n.status}: ${n.statusText}`);
	return n.json();
}
async function cc() {
	return b("/api/results");
}
async function Gf() {
	return b("/api/settings");
}
async function Xf() {
	return b("/api/providers");
}
async function Zf() {
	return b("/api/agent-routes");
}
async function Jf() {
	return b("/api/agent-names");
}
async function qf() {
	return b("/api/worlds");
}
async function bf(e) {
	return b("/api/orchestrate", {
		method: "POST",
		body: JSON.stringify({ worlds: e }),
	});
}
async function ep() {
	return b("/api/worlds/research-unexplored", { method: "POST" });
}
async function tp(e, t = !0) {
	return b("/api/worlds", {
		method: "POST",
		body: JSON.stringify({ world_name: e, auto_research: t }),
	});
}
async function np() {
	return b("/api/worlds/clear-explored", { method: "POST" });
}
async function rp(e) {
	return b(`/api/worlds/${e}/clear-explored`, { method: "POST" });
}
async function lp(e, t) {
	return b("/api/focused-search", {
		method: "POST",
		body: JSON.stringify({ world_name: e, feature: t }),
	});
}
async function Zl(e, t) {
	return b("/api/settings/general", {
		method: "POST",
		body: JSON.stringify({ key: e, value: t }),
	});
}
async function Gs(e) {
	return b("/api/providers", { method: "POST", body: JSON.stringify(e) });
}
async function ip(e) {
	return b("/api/providers/keys", { method: "POST", body: JSON.stringify(e) });
}
async function op(e) {
	return b(`/api/providers/keys/${e}`, { method: "DELETE" });
}
async function sp(e) {
	return b("/api/agent-routes", { method: "POST", body: JSON.stringify(e) });
}
async function up(e) {
	return b(`/api/agent-routes/${e}`, { method: "DELETE" });
}
async function ap() {
	return b("/api/reset-database", { method: "POST" });
}
async function cp() {
	return b("/api/clear-logs", { method: "POST" });
}
function dp(e) {
	return new EventSource(`${ac}/api/logs/${e}`);
}
function fp({ log: e }) {
	return c.jsxs("div", {
		className: "log-line",
		children: [
			c.jsx("span", { className: "time", children: e.created_at }),
			c.jsx("b", { children: e.node_name }),
			" [",
			e.status,
			"] ",
			e.thought,
		],
	});
}
function pp() {
	const [e, t] = R.useState([]),
		[n, r] = R.useState(""),
		[l, i] = R.useState(null),
		[o, s] = R.useState([]),
		[u, f] = R.useState(!1),
		[v, h] = R.useState(!1),
		[m, g] = R.useState(""),
		[x, E] = R.useState(""),
		[D, p] = R.useState(""),
		[a, d] = R.useState(""),
		[y, N] = R.useState(!1),
		k = R.useCallback(async () => {
			try {
				t(await qf());
			} catch (S) {
				console.error(S);
			}
		}, []);
	R.useEffect(() => {
		k();
	}, [k]),
		R.useEffect(() => {
			if (!l) return;
			s([]), f(!0);
			const S = dp(l);
			return (
				(S.onmessage = (O) => {
					const $ = JSON.parse(O.data);
					if ($.finished) {
						S.close(), f(!1);
						return;
					}
					s((G) => [...G, $]);
				}),
				(S.onerror = () => {
					S.close(), f(!1);
				}),
				() => S.close()
			);
		}, [l]);
	const C = R.useMemo(() => e.filter((S) => !S.is_explored).length, [e]),
		L = R.useMemo(
			() =>
				a ? e.filter((S) => S.name.toLowerCase().includes(a.toLowerCase())) : e,
			[e, a],
		),
		j = y ? L : L.slice(0, 24),
		P = L.length > 24 && !y,
		U = async () => {
			const S = n
				.split(",")
				.map((O) => O.trim())
				.filter(Boolean);
			if (S.length)
				try {
					i((await bf(S)).run_id);
				} catch (O) {
					console.error(O);
				}
		},
		fe = async () => {
			try {
				const S = await ep();
				S.run_id && i(S.run_id);
			} catch (S) {
				console.error(S);
			}
		},
		Ye = async () => {
			if (m.trim()) {
				h(!0);
				try {
					await tp(m.trim()), g(""), await k();
				} finally {
					h(!1);
				}
			}
		},
		$t = async () => {
			try {
				await np(), await k();
			} catch (S) {
				console.error(S);
			}
		},
		wn = async (S) => {
			await rp(S), await k();
		},
		Et = async () => {
			if (!(!x.trim() || !D.trim()))
				try {
					i((await lp(x.trim(), D.trim())).run_id);
				} catch (S) {
					console.error(S);
				}
		},
		Ct = async () => {
			try {
				await ap(), await k();
			} catch (S) {
				console.error(S);
			}
		},
		_ = async () => {
			await cp(), s([]);
		};
	return c.jsxs(c.Fragment, {
		children: [
			c.jsxs("section", {
				className: "panel-grid",
				children: [
					c.jsxs("div", {
						className: "panel",
						children: [
							c.jsx("h1", { children: "Orchestration" }),
							c.jsx("p", {
								children:
									"Add worlds, run research loop, stream agent execution.",
							}),
							c.jsx("textarea", {
								value: n,
								onChange: (S) => r(S.target.value),
								placeholder: "Warhammer 40k, Star Wars, Harry Potter",
							}),
							c.jsx("p", {
								className: "help-text",
								children:
									"Comma-separated world names. Each one runs the full research → tier pipeline.",
							}),
							c.jsxs("div", {
								className: "button-row",
								children: [
									c.jsxs("button", {
										className: "primary",
										onClick: U,
										disabled: u,
										children: [
											u
												? c.jsx(Hf, { className: "spin", size: 16 })
												: c.jsx(Kf, { size: 16 }),
											" Run",
										],
									}),
									c.jsxs("button", {
										className: "primary",
										onClick: fe,
										disabled: u,
										children: ["Research All Unexplored (", C, " worlds)"],
									}),
								],
							}),
						],
					}),
					c.jsxs("div", {
						className: "panel terminal",
						children: [
							c.jsxs("div", {
								style: {
									display: "flex",
									justifyContent: "space-between",
									alignItems: "center",
								},
								children: [
									c.jsx("h2", { children: "Live Logs" }),
									c.jsxs("div", {
										style: { display: "flex", gap: 8, alignItems: "center" },
										children: [
											c.jsx("span", {
												className: `status-pill ${u ? "running" : (o.length > 0, "idle")}`,
												children: u
													? "Running"
													: o.some((S) => S.status === "FAILED")
														? "Failed"
														: o.length > 0
															? "Completed"
															: "Idle",
											}),
											c.jsx("button", {
												className: "chip",
												onClick: _,
												children: "Clear Logs",
											}),
										],
									}),
								],
							}),
							o.length === 0
								? c.jsx("p", { className: "muted", children: "No logs yet." })
								: o.map((S, O) => c.jsx(fp, { log: S }, O)),
						],
					}),
				],
			}),
			c.jsxs("section", {
				className: "panel-grid",
				style: { marginTop: 20 },
				children: [
					c.jsxs("div", {
						className: "panel",
						children: [
							c.jsx("h2", { children: "World Registry" }),
							c.jsx("p", {
								className: "help-text",
								children:
									"Manage which worlds exist in the database. Click a world chip to toggle its explored flag.",
							}),
							c.jsxs("div", {
								style: { display: "flex", gap: 8, marginBottom: 12 },
								children: [
									c.jsx("input", {
										value: m,
										onChange: (S) => g(S.target.value),
										placeholder: "Add world to DB",
									}),
									c.jsx("button", {
										className: "primary",
										onClick: Ye,
										disabled: v,
										children: "Add + Research",
									}),
								],
							}),
							c.jsx("input", {
								value: a,
								onChange: (S) => d(S.target.value),
								placeholder: "Search worlds...",
							}),
							c.jsx("button", {
								className: "chip",
								onClick: $t,
								children: "Clear All Explored Flags",
							}),
							c.jsxs("div", {
								className: "chips",
								children: [
									j.map((S) =>
										c.jsxs(
											"button",
											{
												className: S.is_explored ? "chip active" : "chip",
												onClick: () => void wn(S.id),
												children: [S.name, " ", S.is_explored ? "✓" : ""],
											},
											S.id,
										),
									),
									P &&
										c.jsxs("button", {
											className: "chip",
											onClick: () => N(!0),
											children: ["+", L.length - 24, " more"],
										}),
								],
							}),
						],
					}),
					c.jsxs("div", {
						className: "panel",
						children: [
							c.jsx("h2", { children: "Focused Search" }),
							c.jsx("p", {
								className: "help-text",
								children: "Prove or disprove a specific feature about a world.",
							}),
							c.jsx("input", {
								value: x,
								onChange: (S) => E(S.target.value),
								placeholder: "World name",
							}),
							c.jsx("input", {
								value: D,
								onChange: (S) => p(S.target.value),
								placeholder: "Feature to prove/disprove",
							}),
							c.jsx("button", {
								className: "primary",
								onClick: Et,
								disabled: u,
								children: "Focused Search",
							}),
							c.jsx("h2", { children: "Database Controls" }),
							c.jsx("p", {
								className: "muted",
								children: "Reset data, keep settings and seeded worlds.",
							}),
							c.jsx("button", {
								className: "primary",
								onClick: Ct,
								children: "Reset DB",
							}),
						],
					}),
				],
			}),
		],
	});
}
function hp(e) {
	const t = {};
	return (
		e.forEach((n) => {
			const r = n.tier ?? 11;
			t[r] || (t[r] = []), t[r].push(n);
		}),
		Object.entries(t)
			.map(([n, r]) => ({ tier: parseInt(n), worlds: r }))
			.sort((n, r) => n.tier - r.tier)
	);
}
function mp({ world: e, anomalies: t }) {
	const n = t.filter((r) => r.world_id === e.id);
	return c.jsxs("div", {
		children: [
			c.jsxs("div", {
				style: {
					display: "flex",
					justifyContent: "space-between",
					alignItems: "center",
					marginBottom: 16,
				},
				children: [
					c.jsx("h2", { children: e.name }),
					c.jsxs("div", {
						className: "badge",
						style: { fontSize: "1.2rem", padding: "4px 12px" },
						children: ["Tier ", e.tier ?? "null"],
					}),
				],
			}),
			c.jsxs("div", {
				className: "detail-box",
				children: [
					c.jsx("div", {
						className: "detail-label",
						children: "Tier Justification",
					}),
					c.jsx("pre", {
						className: "detail-content",
						children: e.tier_justification ?? "No justification provided.",
					}),
				],
			}),
			n.length > 0 &&
				c.jsxs("div", {
					className: "detail-box",
					style: { marginTop: 16, border: "1px solid #f59e0b" },
					children: [
						c.jsx("div", { className: "detail-label", children: "Anomalies" }),
						n.map((r, l) =>
							c.jsx(
								"pre",
								{ className: "detail-content", children: r.description },
								l,
							),
						),
					],
				}),
			e.theory &&
				c.jsxs("div", {
					className: "detail-box",
					style: { marginTop: 16 },
					children: [
						c.jsx("div", {
							className: "detail-label",
							children: "Ontological Theory",
						}),
						c.jsx("pre", { className: "detail-content", children: e.theory }),
						e.theory_audit &&
							c.jsxs("div", {
								className: "audit-box",
								children: [
									c.jsx("div", {
										className: "audit-label",
										children: "Auditor Feedback",
									}),
									c.jsx("div", {
										className: "audit-content",
										children: e.theory_audit,
									}),
								],
							}),
					],
				}),
		],
	});
}
function vp() {
	const [e, t] = R.useState([]),
		[n, r] = R.useState([]),
		[l, i] = R.useState(null),
		[o, s] = R.useState(null);
	R.useEffect(() => {
		u();
	}, []);
	const u = async () => {
			try {
				const h = await cc();
				i(h.tier_system), t(h.worlds), r(h.anomalies);
			} catch (h) {
				console.error(h);
			}
		},
		f = R.useMemo(() => e.find((h) => h.id === o) ?? null, [e, o]),
		v = hp(e);
	return c.jsxs("section", {
		className: "panel-grid tiers",
		children: [
			c.jsxs("div", {
				className: "panel list",
				children: [
					c.jsx("h1", { children: "Tier System" }),
					c.jsx("p", {
						className: "help-text",
						children:
							"Worlds grouped by assigned tier. Click a world to see details.",
					}),
					l &&
						c.jsxs("div", {
							className: "tier-system-block",
							children: [
								c.jsx("h3", { children: "System Definition" }),
								c.jsx("pre", { className: "tier-system-text", children: l }),
							],
						}),
					!l &&
						c.jsx("p", {
							className: "muted",
							children: "No tier system yet. Run the pipeline to generate one.",
						}),
					v.map(({ tier: h, worlds: m }) =>
						c.jsxs(
							"div",
							{
								className: "tier-row",
								children: [
									c.jsxs("div", {
										className: "tier-label",
										children: ["Tier ", h],
									}),
									c.jsx("div", {
										className: "chips",
										children: m.length
											? m.map((g) =>
													c.jsx(
														"button",
														{
															className: o === g.id ? "chip active" : "chip",
															onClick: () => s(g.id),
															children: g.name,
														},
														g.id,
													),
												)
											: c.jsx("span", {
													className: "muted",
													children: "Empty",
												}),
									}),
								],
							},
							h,
						),
					),
				],
			}),
			c.jsxs("div", {
				className: "panel detail",
				children: [
					f
						? c.jsx(mp, { world: f, anomalies: n })
						: c.jsx("p", {
								className: "muted",
								children: "Select a world to view details.",
							}),
					n.filter((h) => h.world_id === null).length > 0 &&
						c.jsxs("div", {
							className: "anomaly-list",
							style: { marginTop: 16 },
							children: [
								c.jsx("h4", { children: "Global Anomalies" }),
								n
									.filter((h) => h.world_id === null)
									.map((h, m) =>
										c.jsx(
											"div",
											{ className: "anomaly", children: h.description },
											m,
										),
									),
							],
						}),
				],
			}),
		],
	});
}
function yp() {
	const [e, t] = R.useState([]);
	R.useEffect(() => {
		n();
	}, []);
	const n = async () => {
			try {
				const l = await cc();
				t(l.worlds);
			} catch (l) {
				console.error(l);
			}
		},
		r = e.filter((l) => l.theory);
	return c.jsx("section", {
		className: "panel-grid single",
		children: c.jsxs("div", {
			className: "panel",
			children: [
				c.jsx("h1", { children: "Ontological Theories" }),
				c.jsx("p", {
					className: "help-text",
					children:
						"Generated after tiering completes — extrapolated interactions grounded in verified research, each with an auditor verdict.",
				}),
				r.map((l) =>
					c.jsxs(
						"div",
						{
							className: "theory-card",
							children: [
								c.jsxs("div", {
									style: {
										display: "flex",
										justifyContent: "space-between",
										alignItems: "center",
										marginBottom: 12,
									},
									children: [
										c.jsx("h3", { children: l.name }),
										c.jsxs("div", {
											className: "badge",
											children: ["Tier ", l.tier ?? "null"],
										}),
									],
								}),
								c.jsx("div", {
									className: "theory-body",
									children: c.jsx("pre", { children: l.theory }),
								}),
								l.theory_audit &&
									c.jsxs("div", {
										className: "theory-audit",
										children: [
											c.jsx("div", {
												className: "audit-label",
												children: "Auditor Verdict",
											}),
											c.jsx("div", {
												className: "audit-text",
												children: l.theory_audit,
											}),
										],
									}),
							],
						},
						l.id,
					),
				),
				r.length === 0 &&
					c.jsx("p", {
						className: "muted",
						children:
							"No theories generated yet. Run the full pipeline to extrapolate interactions.",
					}),
			],
		}),
	});
}
const gp = "●●●●●●●●●●●●",
	wp = [
		{ value: "openai", label: "OpenAI" },
		{ value: "anthropic", label: "Anthropic" },
		{ value: "gemini", label: "Gemini" },
		{ value: "ollama", label: "Ollama" },
		{ value: "groq", label: "Groq" },
		{ value: "openrouter", label: "OpenRouter" },
		{ value: "custom", label: "Custom" },
	];
function Sp({
	provider: e,
	onSave: t,
	onSaveKey: n,
	onDeleteKey: r,
	onDeleteProvider: l,
}) {
	var We;
	const [i, o] = R.useState(e.name),
		[s, u] = R.useState(!1),
		[f, v] = R.useState(e.base_url ?? ""),
		[h, m] = R.useState(!1),
		[g, x] = R.useState(
			(e.models ?? "")
				.split(",")
				.map((z) => z.trim())
				.filter(Boolean),
		),
		[E, D] = R.useState(""),
		[p, a] = R.useState(!1),
		[d, y] = R.useState(e.keys),
		[N, k] = R.useState(null),
		[C, L] = R.useState(new Set()),
		[j, P] = R.useState(null),
		[U, fe] = R.useState(!1),
		Ye = async () => {
			if (i.trim()) {
				u(!0);
				try {
					await t({
						id: e.id,
						name: i,
						provider_type: e.provider_type,
						base_url: e.base_url,
						models: e.models,
					});
				} finally {
					u(!1);
				}
			}
		},
		$t = async () => {
			m(!0);
			try {
				await t({
					id: e.id,
					name: e.name,
					provider_type: e.provider_type,
					base_url: f || null,
					models: e.models,
				});
			} finally {
				m(!1);
			}
		},
		wn = async () => {
			a(!0);
			try {
				await t({
					id: e.id,
					name: e.name,
					provider_type: e.provider_type,
					base_url: e.base_url,
					models: g.join(",") || null,
				});
			} finally {
				a(!1);
			}
		},
		Et = () => {
			const z = E.trim();
			z && !g.includes(z) && x([...g, z]), D("");
		},
		Ct = (z) => {
			x(g.filter((F) => F !== z));
		},
		_ = async (z) => {
			L((F) => new Set(F).add(z.id));
			try {
				const F = await n({
					id: z.id,
					provider_id: z.provider_id,
					api_key: z.api_key,
					priority: z.priority,
				});
				y((Z) =>
					Z.map((le) =>
						le.id === z.id
							? { ...le, id: (F == null ? void 0 : F.id) ?? z.id }
							: le,
					),
				);
			} finally {
				L((F) => {
					const Z = new Set(F);
					return Z.delete(z.id), Z;
				}),
					k(null);
			}
		},
		S = async (z) => {
			try {
				await r(z), y((F) => F.filter((Z) => Z.id !== z));
			} catch {
				console.error("Failed to delete key");
			} finally {
				P(null);
			}
		},
		O = (z, F) => {
			const Z = z + F;
			if (Z < 0 || Z >= d.length) return;
			const le = [...d];
			([le[z], le[Z]] = [le[Z], le[z]]),
				(le[z] = { ...le[z], priority: z }),
				(le[Z] = { ...le[Z], priority: Z }),
				y(le);
		},
		$ = async () => {
			const z = -(d.length + 1),
				F = { id: z, provider_id: e.id, api_key: "", priority: d.length };
			y([...d, F]), k(z);
		},
		G = d.length > 1,
		Wt = d.length;
	return c.jsxs("div", {
		className: "provider-card",
		children: [
			c.jsxs("div", {
				className: "provider-card-header",
				children: [
					c.jsxs("div", {
						className: "provider-identity-section",
						children: [
							c.jsx("input", {
								className: "provider-name",
								value: i,
								onChange: (z) => o(z.target.value),
								placeholder: "Provider name",
							}),
							c.jsx("span", {
								className: "provider-type-badge",
								children:
									((We = wp.find((z) => z.value === e.provider_type)) == null
										? void 0
										: We.label) ??
									e.provider_type ??
									"No type",
							}),
							c.jsx("button", {
								className: "chip",
								onClick: Ye,
								disabled: s || !i.trim(),
								children: s ? "..." : "Save Name",
							}),
							U
								? c.jsxs("span", {
										className: "confirm-delete",
										children: [
											"Delete provider?",
											" ",
											c.jsx("button", {
												className: "chip delete",
												onClick: async () => {
													await (l == null ? void 0 : l(e.id)), fe(!1);
												},
												children: "Yes",
											}),
											c.jsx("button", {
												className: "chip",
												onClick: () => fe(!1),
												children: "No",
											}),
										],
									})
								: c.jsx("button", {
										className: "chip delete",
										onClick: () => fe(!0),
										disabled: !l,
										children: "Delete",
									}),
						],
					}),
					Wt === 0 &&
						c.jsx("span", {
							className: "badge-warning",
							children:
								"⚠ 0 keys — routing steps using this provider will be skipped",
						}),
				],
			}),
			c.jsxs("div", {
				className: "provider-card-body",
				children: [
					c.jsxs("div", {
						className: "provider-section",
						children: [
							c.jsx("h4", { children: "Connection" }),
							c.jsxs("label", {
								className: "field",
								children: [
									c.jsx("span", { children: "Base URL" }),
									c.jsx("input", {
										value: f,
										onChange: (z) => v(z.target.value),
										placeholder: "https://api.openai.com/v1",
									}),
									c.jsx("p", {
										className: "help-text",
										children:
											"Leave blank to use provider's default endpoint. Only needed for Ollama, OpenRouter, or self-hosted setups.",
									}),
								],
							}),
							c.jsx("button", {
								className: "chip",
								onClick: $t,
								disabled: h,
								children: h ? "..." : "Save",
							}),
						],
					}),
					c.jsxs("div", {
						className: "provider-section",
						children: [
							c.jsx("h4", { children: "Models this provider can serve" }),
							c.jsxs("div", {
								className: "models-tags",
								children: [
									g.map((z) =>
										c.jsxs(
											"span",
											{
												className: "tag",
												children: [
													z,
													c.jsx("button", {
														className: "tag-remove",
														onClick: () => Ct(z),
														children: "×",
													}),
												],
											},
											z,
										),
									),
									c.jsx("span", {
										className: "tag-input-wrap",
										children: c.jsx("input", {
											value: E,
											onChange: (z) => D(z.target.value),
											onKeyDown: (z) => {
												z.key === "Enter" && (z.preventDefault(), Et());
											},
											placeholder: "+ add model",
											className: "tag-input",
										}),
									}),
								],
							}),
							c.jsx("p", {
								className: "help-text",
								children:
									"These become the model choices when you build routing rules for this provider. Enter model names and press Enter to add.",
							}),
							c.jsx("button", {
								className: "chip",
								onClick: wn,
								disabled: p,
								children: p ? "..." : "Save",
							}),
						],
					}),
					c.jsxs("div", {
						className: "provider-section",
						children: [
							c.jsx("h4", {
								children: "API Keys (tried in order, top to bottom)",
							}),
							c.jsx("p", {
								className: "help-text",
								children:
									"If a key fails or hits a rate limit, the next one is tried automatically.",
							}),
							c.jsx("div", {
								className: "keys-list",
								children: d
									.sort((z, F) => z.priority - F.priority)
									.map((z, F) =>
										c.jsxs(
											"div",
											{
												className: "key-row",
												children: [
													c.jsxs("span", {
														className: "key-index",
														children: [F + 1, "."],
													}),
													N === z.id
														? c.jsxs(c.Fragment, {
																children: [
																	c.jsx("input", {
																		type: "password",
																		value: z.api_key,
																		onChange: (Z) => {
																			const le = [...d];
																			(le[F] = {
																				...le[F],
																				api_key: Z.target.value,
																			}),
																				y(le);
																		},
																		placeholder: "API Key",
																		autoFocus: !0,
																	}),
																	c.jsx("button", {
																		className: "chip",
																		onClick: () => _(z),
																		disabled: C.has(z.id),
																		children: C.has(z.id) ? "..." : "Save",
																	}),
																	c.jsx("button", {
																		className: "chip",
																		onClick: () => k(null),
																		children: "Cancel",
																	}),
																],
															})
														: c.jsxs(c.Fragment, {
																children: [
																	c.jsx("span", {
																		className: "key-value",
																		children: z.api_key
																			? gp + z.api_key.slice(-4)
																			: "(empty)",
																	}),
																	c.jsx("button", {
																		className: "chip",
																		onClick: () => k(z.id),
																		children: "Edit",
																	}),
																	G &&
																		c.jsxs(c.Fragment, {
																			children: [
																				c.jsx("button", {
																					className: "chip",
																					onClick: () => O(F, -1),
																					disabled: F === 0,
																					children: "↑",
																				}),
																				c.jsx("button", {
																					className: "chip",
																					onClick: () => O(F, 1),
																					disabled: F === d.length - 1,
																					children: "↓",
																				}),
																			],
																		}),
																	j === z.id
																		? c.jsxs("span", {
																				className: "confirm-delete",
																				children: [
																					c.jsx("button", {
																						className: "chip delete",
																						onClick: () => S(z.id),
																						children: "Confirm",
																					}),
																					c.jsx("button", {
																						className: "chip",
																						onClick: () => P(null),
																						children: "Cancel",
																					}),
																				],
																			})
																		: c.jsx("button", {
																				className: "chip delete",
																				onClick: () => P(z.id),
																				children: "×",
																			}),
																],
															}),
												],
											},
											z.id,
										),
									),
							}),
							c.jsx("button", {
								className: "chip",
								onClick: $,
								children: "+ Add Fallback Key",
							}),
						],
					}),
				],
			}),
		],
	});
}
function Xs({
	agentName: e,
	routes: t,
	providers: n,
	onSave: r,
	onDelete: l,
	defaultRoutes: i,
}) {
	const [o, s] = R.useState(e === "DEFAULT"),
		[u, f] = R.useState(t),
		v = e === "DEFAULT",
		h = t.length > 0,
		m = (i == null ? void 0 : i.length) ?? 0,
		g = v
			? `${t.length} step(s)`
			: h
				? `${t.length} custom step(s)`
				: `Using DEFAULT (${m} step(s))`,
		x = (a, d, y) => {
			const N = [...u];
			(N[a] = { ...N[a], [d]: y }), f(N);
		},
		E = async (a) => {
			await r(u[a]);
		},
		D = [];
	u.forEach((a) => {
		const d = n.find((N) => N.id === a.provider_id);
		if (!d) return;
		const y = (a.models || d.models || "")
			.split(",")
			.map((N) => N.trim())
			.filter(Boolean);
		d.keys.forEach((N, k) => {
			y.forEach((C) => {
				D.push({ provider: d.name, keyLabel: `Key ${k + 1}`, model: C });
			});
		});
	});
	const p = async () => {
		if (!i) return;
		const a = [];
		for (const d of i) {
			const y = await r({
				id: 0,
				task_type: e,
				provider_id: d.provider_id,
				models: d.models,
				priority: d.priority,
			});
			y && a.push(y);
		}
		f((d) => [...d, ...a]);
	};
	return c.jsxs("div", {
		className: `routing-card ${o ? "expanded" : ""}`,
		children: [
			c.jsxs("div", {
				className: "routing-card-header",
				onClick: () => s(!o),
				children: [
					c.jsxs("div", {
						className: "routing-card-title",
						children: [
							c.jsx("span", {
								className: "agent-name",
								children: v ? "DEFAULT" : e,
							}),
							c.jsx("span", { className: "agent-status", children: g }),
						],
					}),
					c.jsxs("div", {
						className: "routing-card-actions",
						children: [
							!v &&
								!h &&
								i &&
								c.jsx("button", {
									className: "chip",
									onClick: (a) => {
										a.stopPropagation(), p();
									},
									children: "Override",
								}),
							c.jsx("span", {
								className: "expand-icon",
								children: o ? "▲" : "▼",
							}),
						],
					}),
				],
			}),
			o &&
				c.jsxs("div", {
					className: "routing-card-body",
					children: [
						c.jsx("p", {
							className: "help-text",
							children:
								"Each agent tries its fallback chain top to bottom: provider → its keys in order → its models in order. If everything fails, the run fails that step. Agents without their own chain use the DEFAULT chain.",
						}),
						D.length > 0 &&
							c.jsxs("div", {
								className: "resolved-sequence",
								children: [
									c.jsx("h4", { children: "Resolved Fallback Order:" }),
									c.jsx("ol", {
										className: "sequence-list",
										children: D.map((a, d) =>
											c.jsxs(
												"li",
												{
													className: "sequence-item",
													children: [
														a.provider,
														" → ",
														a.keyLabel,
														" → ",
														a.model,
													],
												},
												d,
											),
										),
									}),
								],
							}),
						c.jsx("hr", { className: "routing-divider" }),
						c.jsxs("div", {
							className: "route-slots",
							children: [
								u.map((a, d) => {
									var N;
									const y =
										((N = n.find((k) => k.id === a.provider_id)) == null
											? void 0
											: N.models) ?? "";
									return c.jsxs(
										"div",
										{
											className: "route-slot",
											children: [
												c.jsxs("span", {
													className: "slot-num",
													children: ["#", d + 1],
												}),
												c.jsxs("select", {
													value: a.provider_id ?? "",
													onChange: (k) =>
														x(
															d,
															"provider_id",
															k.target.value ? Number(k.target.value) : null,
														),
													children: [
														c.jsx("option", {
															value: "",
															children: "Select Provider",
														}),
														n.map((k) =>
															c.jsx(
																"option",
																{ value: k.id, children: k.name },
																k.id,
															),
														),
													],
												}),
												c.jsx("input", {
													value: a.models ?? "",
													onChange: (k) =>
														x(d, "models", k.target.value || null),
													placeholder: `Models CSV (default: ${y || "none"})`,
													className: "route-models-input",
												}),
												c.jsxs("div", {
													className: "slot-actions",
													children: [
														c.jsx("button", {
															className: "chip",
															onClick: () => void E(d),
															children: "Save",
														}),
														c.jsx("button", {
															className: "chip delete",
															onClick: async () => {
																await l(a.id),
																	f((k) => k.filter((C) => C.id !== a.id));
															},
															children: "×",
														}),
													],
												}),
											],
										},
										a.id,
									);
								}),
								c.jsx("button", {
									className: "chip add-slot",
									onClick: async () => {
										const a = await r({
											id: 0,
											task_type: e,
											provider_id: null,
											models: null,
											priority: u.length,
										});
										a && f((d) => [...d, a]);
									},
									children: "+ Add Provider Step",
								}),
							],
						}),
					],
				}),
		],
	});
}
function kp({ keyName: e, value: t, onSave: n, onDelete: r }) {
	const [l, i] = R.useState(t),
		[o, s] = R.useState(!1),
		[u, f] = R.useState(!1),
		v = async () => {
			s(!0);
			try {
				await n(e, l);
			} finally {
				s(!1);
			}
		};
	return c.jsxs("div", {
		className: "setting-item",
		children: [
			c.jsx("span", { className: "setting-key", children: e }),
			c.jsx("input", {
				value: l,
				onChange: (h) => i(h.target.value),
				className: "setting-value",
			}),
			c.jsx("button", {
				className: "chip",
				onClick: v,
				disabled: o,
				children: o ? "..." : "Save",
			}),
			u
				? c.jsxs("span", {
						className: "confirm-delete",
						children: [
							c.jsx("button", {
								className: "chip delete",
								onClick: async () => {
									await r(e), f(!1);
								},
								children: "Confirm",
							}),
							c.jsx("button", {
								className: "chip",
								onClick: () => f(!1),
								children: "Cancel",
							}),
						],
					})
				: c.jsx("button", {
						className: "chip delete",
						onClick: () => f(!0),
						children: "×",
					}),
		],
	});
}
function xp() {
	const [e, t] = R.useState("providers"),
		[n, r] = R.useState([]),
		[l, i] = R.useState([]),
		[o, s] = R.useState([]),
		[u, f] = R.useState({}),
		[v, h] = R.useState(""),
		[m, g] = R.useState(!1);
	R.useEffect(() => {
		x();
	}, []);
	const x = async () => {
			try {
				const [j, P, U, fe] = await Promise.all([Gf(), Xf(), Zf(), Jf()]);
				f(j.general_settings), r(P), i(U), s(fe);
			} catch (j) {
				console.error("Failed to refresh settings:", j);
			}
		},
		E = async (j) => {
			try {
				await Gs(j);
			} catch (P) {
				console.error("Failed to save provider:", P);
			}
		},
		D = async (j) => {
			try {
				return await ip(j);
			} catch (P) {
				console.error("Failed to save key:", P);
			}
		},
		p = async (j) => {
			try {
				await op(j);
			} catch (P) {
				console.error("Failed to delete key:", P);
			}
		},
		a = async (j) => {
			try {
				return await sp(j);
			} catch (P) {
				console.error("Failed to save route:", P);
			}
		},
		d = async (j) => {
			try {
				await up(j);
			} catch (P) {
				console.error("Failed to delete route:", P);
			}
		},
		y = async (j, P) => {
			try {
				await Zl(j, P), f((U) => ({ ...U, [j]: P }));
			} catch (U) {
				console.error("Failed to save setting:", U);
			}
		},
		N = async (j) => {
			try {
				await Zl(j, null),
					f((P) => {
						const U = { ...P };
						return delete U[j], U;
					});
			} catch (P) {
				console.error("Failed to delete setting:", P);
			}
		},
		k = async () => {
			if (v.trim()) {
				g(!0);
				try {
					await Zl(v.trim(), null),
						f((j) => ({ ...j, [v.trim()]: null })),
						h("");
				} finally {
					g(!1);
				}
			}
		},
		C = async () => {
			try {
				await Gs({
					id: 0,
					name: `New Provider ${Date.now()}`,
					provider_type: null,
					base_url: null,
					models: null,
				}),
					await x();
			} catch (j) {
				console.error("Failed to add provider:", j);
			}
		},
		L = l
			.filter((j) => j.task_type === "DEFAULT")
			.sort((j, P) => j.priority - P.priority);
	return c.jsxs("section", {
		className: "panel-grid settings-grid",
		children: [
			c.jsxs("div", {
				className: "settings-tabs",
				children: [
					c.jsx("button", {
						className: e === "providers" ? "tab active" : "tab",
						onClick: () => t("providers"),
						children: "Providers & Keys",
					}),
					c.jsx("button", {
						className: e === "routing" ? "tab active" : "tab",
						onClick: () => t("routing"),
						children: "Agent Routing",
					}),
					c.jsx("button", {
						className: e === "general" ? "tab active" : "tab",
						onClick: () => t("general"),
						children: "General",
					}),
				],
			}),
			e === "providers" &&
				c.jsxs("div", {
					className: "settings-content",
					children: [
						c.jsx("h2", { children: "Providers & Keys" }),
						c.jsx("p", {
							className: "muted",
							children: "Define LLM providers and their fallback API keys.",
						}),
						c.jsx("button", {
							className: "primary",
							onClick: C,
							children: "+ Add Provider",
						}),
						c.jsx("div", {
							className: "provider-list",
							children: n.map((j) =>
								c.jsx(
									Sp,
									{ provider: j, onSave: E, onSaveKey: D, onDeleteKey: p },
									j.id,
								),
							),
						}),
					],
				}),
			e === "routing" &&
				c.jsxs("div", {
					className: "settings-content",
					children: [
						c.jsx("h2", { children: "Agent Routing" }),
						c.jsx("p", {
							className: "muted",
							children:
								"Each agent tries its fallback chain top to bottom: provider → its keys in order → its models in order. If everything fails, the run fails that step. Agents without their own chain use the DEFAULT chain below.",
						}),
						c.jsxs("div", {
							className: "routing-list",
							children: [
								c.jsx(Xs, {
									agentName: "DEFAULT",
									routes: L,
									providers: n,
									onSave: a,
									onDelete: d,
								}),
								c.jsx("hr", { className: "routing-divider" }),
								o.map((j) => {
									const P = l
										.filter((U) => U.task_type === j)
										.sort((U, fe) => U.priority - fe.priority);
									return c.jsx(
										Xs,
										{
											agentName: j,
											routes: P,
											providers: n,
											onSave: a,
											onDelete: d,
											defaultRoutes: L,
										},
										j,
									);
								}),
							],
						}),
					],
				}),
			e === "general" &&
				c.jsxs("div", {
					className: "settings-content",
					children: [
						c.jsx("h2", { children: "General Settings" }),
						c.jsx("p", {
							className: "muted",
							children:
								"Free-form key/value pairs used by custom agent prompts or integrations.",
						}),
						c.jsxs("div", {
							className: "add-setting-row",
							children: [
								c.jsx("input", {
									value: v,
									onChange: (j) => h(j.target.value),
									onKeyDown: (j) => {
										j.key === "Enter" && k();
									},
									placeholder: "Setting Key (e.g. API_KEY)",
								}),
								c.jsx("button", {
									className: "primary",
									onClick: k,
									disabled: m || !v.trim(),
									children: m ? "..." : "Add Key",
								}),
							],
						}),
						c.jsx("div", {
							className: "settings-list",
							children: Object.entries(u).map(([j, P]) =>
								c.jsx(
									kp,
									{ keyName: j, value: P ?? "", onSave: y, onDelete: N },
									j,
								),
							),
						}),
					],
				}),
		],
	});
}
const Np = [
	{ id: "dashboard", label: "Command Center", Icon: Yf },
	{ id: "database", label: "Tiers", Icon: uc },
	{ id: "theories", label: "Theories", Icon: Vf },
	{ id: "settings", label: "Settings", Icon: Qf },
];
function Ep() {
	const [e, t] = R.useState("dashboard");
	return c.jsxs("div", {
		className: "app-shell",
		children: [
			c.jsxs("aside", {
				className: "sidebar",
				children: [
					c.jsxs("div", {
						className: "brand",
						children: [
							c.jsx(uc, {}),
							c.jsxs("div", {
								children: [
									c.jsx("div", {
										className: "brand-title",
										children: "OMNIVERSE 2",
									}),
									c.jsx("div", {
										className: "brand-sub",
										children: "LangGraph command center",
									}),
								],
							}),
						],
					}),
					c.jsx("nav", {
						className: "nav",
						children: Np.map(({ id: n, label: r, Icon: l }) =>
							c.jsxs(
								"button",
								{
									className: e === n ? "nav-item active" : "nav-item",
									onClick: () => t(n),
									children: [c.jsx(l, { size: 16 }), " ", r],
								},
								n,
							),
						),
					}),
				],
			}),
			c.jsxs("main", {
				className: "main",
				children: [
					e === "dashboard" && c.jsx(pp, {}),
					e === "database" && c.jsx(vp, {}),
					e === "theories" && c.jsx(yp, {}),
					e === "settings" && c.jsx(xp, {}),
				],
			}),
		],
	});
}
Jl.createRoot(document.getElementById("root")).render(
	c.jsx(jc.StrictMode, { children: c.jsx(Ep, {}) }),
);
