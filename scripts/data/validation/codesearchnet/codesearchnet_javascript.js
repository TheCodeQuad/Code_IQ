// =============================================================================
// Auto-generated from CodeSearchNet JavaScript dataset
// Total functions: 100
// Each function has its ORIGINAL comment as a JSDoc block above it.
// Feed this file through the Code_IQ pipeline to generate NEW docstrings,
// then compare original vs generated.
// =============================================================================
'use strict';

// --- [1/100] createTypeScriptLanguageService (Microsoft/vscode) ---

/**
 * #region Discovery, LanguageService & Setup
 * @original_repo Microsoft/vscode
 * @original_name createTypeScriptLanguageService
 */
function createTypeScriptLanguageService(options) {
    // Discover referenced files
    const FILES = discoverAndReadFiles(options);
    // Add fake usage files
    options.inlineEntryPoints.forEach((inlineEntryPoint, index) => {
        FILES[`inlineEntryPoint.${index}.ts`] = inlineEntryPoint;
    });
    // Add additional typings
    options.typings.forEach((typing) => {
        const filePath = path.join(options.sourcesRoot, typing);
        FILES[typing] = fs.readFileSync(filePath).toString();
    });
    // Resolve libs
    const RESOLVED_LIBS = {};
    options.libs.forEach((filename) => {
        const filepath = path.join(TYPESCRIPT_LIB_FOLDER, filename);
        RESOLVED_LIBS[`defaultLib:${filename}`] = fs.readFileSync(filepath).toString();
    });
    const compilerOptions = ts.convertCompilerOptionsFromJson(options.compilerOptions, options.sourcesRoot).options;
    const host = new TypeScriptLanguageServiceHost(RESOLVED_LIBS, FILES, compilerOptions);
    return ts.createLanguageService(host);
}

// --- [2/100] discoverAndReadFiles (Microsoft/vscode) ---

/**
 * Read imports and follow them until all files have been handled
 * @original_repo Microsoft/vscode
 * @original_name discoverAndReadFiles
 */
function discoverAndReadFiles(options) {
    const FILES = {};
    const in_queue = Object.create(null);
    const queue = [];
    const enqueue = (moduleId) => {
        if (in_queue[moduleId]) {
            return;
        }
        in_queue[moduleId] = true;
        queue.push(moduleId);
    };
    options.entryPoints.forEach((entryPoint) => enqueue(entryPoint));
    while (queue.length > 0) {
        const moduleId = queue.shift();
        const dts_filename = path.join(options.sourcesRoot, moduleId + '.d.ts');
        if (fs.existsSync(dts_filename)) {
            const dts_filecontents = fs.readFileSync(dts_filename).toString();
            FILES[`${moduleId}.d.ts`] = dts_filecontents;
            continue;
        }
        const js_filename = path.join(options.sourcesRoot, moduleId + '.js');
        if (fs.existsSync(js_filename)) {
            // This is an import for a .js file, so ignore it...
            continue;
        }
        let ts_filename;
        if (options.redirects[moduleId]) {
            ts_filename = path.join(options.sourcesRoot, options.redirects[moduleId] + '.ts');
        }
        else {
            ts_filename = path.join(options.sourcesRoot, moduleId + '.ts');
        }
        const ts_filecontents = fs.readFileSync(ts_filename).toString();
        const info = ts.preProcessFile(ts_filecontents);
        for (let i = info.importedFiles.length - 1; i >= 0; i--) {
            const importedFileName = info.importedFiles[i].fileName;
            if (options.importIgnorePattern.test(importedFileName)) {
                // Ignore vs/css! imports
                continue;
            }
            let importedModuleId = importedFileName;
            if (/(^\.\/)|(^\.\.\/)/.test(importedModuleId)) {
                importedModuleId = path.join(path.dirname(moduleId), importedModuleId);
            }
            enqueue(importedModuleId);
        }
        FILES[`${moduleId}.ts`] = ts_filecontents;
    }
    return FILES;
}

// --- [3/100] getRealNodeSymbol (Microsoft/vscode) ---

/**
 * #endregion #region Utils
 * Returns the node's symbol and the `import` node (if the symbol resolved from a different module)
 * @original_repo Microsoft/vscode
 * @original_name getRealNodeSymbol
 */
function getRealNodeSymbol(checker, node) {
    const getPropertySymbolsFromContextualType = ts.getPropertySymbolsFromContextualType;
    const getContainingObjectLiteralElement = ts.getContainingObjectLiteralElement;
    const getNameFromPropertyName = ts.getNameFromPropertyName;
    // Go to the original declaration for cases:
    //
    //   (1) when the aliased symbol was declared in the location(parent).
    //   (2) when the aliased symbol is originating from an import.
    //
    function shouldSkipAlias(node, declaration) {
        if (node.kind !== ts.SyntaxKind.Identifier) {
            return false;
        }
        if (node.parent === declaration) {
            return true;
        }
        switch (declaration.kind) {
            case ts.SyntaxKind.ImportClause:
            case ts.SyntaxKind.ImportEqualsDeclaration:
                return true;
            case ts.SyntaxKind.ImportSpecifier:
                return declaration.parent.kind === ts.SyntaxKind.NamedImports;
            default:
                return false;
        }
    }
    if (!ts.isShorthandPropertyAssignment(node)) {
        if (node.getChildCount() !== 0) {
            return [null, null];
        }
    }
    const { parent } = node;
    let symbol = checker.getSymbolAtLocation(node);
    let importNode = null;
    // If this is an alias, and the request came at the declaration location
    // get the aliased symbol instead. This allows for goto def on an import e.g.
    //   import {A, B} from "mod";
    // to jump to the implementation directly.
    if (symbol && symbol.flags & ts.SymbolFlags.Alias && shouldSkipAlias(node, symbol.declarations[0])) {
        const aliased = checker.getAliasedSymbol(symbol);
        if (aliased.declarations) {
            // We should mark the import as visited
            importNode = symbol.declarations[0];
            symbol = aliased;
        }
    }
    if (symbol) {
        // Because name in short-hand property assignment has two different meanings: property name and property value,
        // using go-to-definition at such position should go to the variable declaration of the property value rather than
        // go to the declaration of the property name (in this case stay at the same position). However, if go-to-definition
        // is performed at the location of property access, we would like to go to definition of the property in the short-hand
        // assignment. This case and others are handled by the following code.
        if (node.parent.kind === ts.SyntaxKind.ShorthandPropertyAssignment) {
            symbol = checker.getShorthandAssignmentValueSymbol(symbol.valueDeclaration);
        }
        // If the node is the name of a BindingElement within an ObjectBindingPattern instead of just returning the
        // declaration the symbol (which is itself), we should try to get to the original type of the ObjectBindingPattern
        // and return the property declaration for the referenced property.
        // For example:
        //      import('./foo').then(({ b/*goto*/ar }) => undefined); => should get use to the declaration in file "./foo"
        //
        //      function bar<T>(onfulfilled: (value: T) => void) { //....}
        //      interface Test {
        //          pr/*destination*/op1: number
        //      }
        //      bar<Test>(({pr/*goto*/op1})=>{});
        if (ts.isPropertyName(node) && ts.isBindingElement(parent) && ts.isObjectBindingPattern(parent.parent) &&
            (node === (parent.propertyName || parent.name))) {
            const name = getNameFromPropertyName(node);
            const type = checker.getTypeAtLocation(parent.parent);
            if (name && type) {
                if (type.isUnion()) {
                    const prop = type.types[0].getProperty(name);
                    if (prop) {
                        symbol = prop;
                    }
                }
                else {
                    const prop = type.getProperty(name);
                    if (prop) {
                        symbol = prop;
                    }
                }
            }
        }
        // If the current location we want to find its definition is in an object literal, try to get the contextual type for the
        // object literal, lookup the property symbol in the contextual type, and use this for goto-definition.
        // For example
        //      interface Props{
        //          /*first*/prop1: number
        //          prop2: boolean
        //      }
        //      function Foo(arg: Props) {}
        //      Foo( { pr/*1*/op1: 10, prop2: false })
        const element = getContainingObjectLiteralElement(node);
        if (element) {
            const contextualType = element && checker.getContextualType(element.parent);
            if (contextualType) {
                const propertySymbols = getPropertySymbolsFromContextualType(element, checker, contextualType, /*unionSymbolOk*/ false);
                if (propertySymbols) {
                    symbol = propertySymbols[0];
                }
            }
        }
    }
    if (symbol && symbol.declarations) {
        return [symbol, importNode];
    }
    return [null, null];
}

// --- [4/100] shouldSkipAlias (Microsoft/vscode) ---

/**
 * Go to the original declaration for cases:  (1) when the aliased symbol was declared in the location(parent). (2) when the aliased symbol is originating from an import.
 * @original_repo Microsoft/vscode
 * @original_name shouldSkipAlias
 */
function shouldSkipAlias(node, declaration) {
        if (node.kind !== ts.SyntaxKind.Identifier) {
            return false;
        }
        if (node.parent === declaration) {
            return true;
        }
        switch (declaration.kind) {
            case ts.SyntaxKind.ImportClause:
            case ts.SyntaxKind.ImportEqualsDeclaration:
                return true;
            case ts.SyntaxKind.ImportSpecifier:
                return declaration.parent.kind === ts.SyntaxKind.NamedImports;
            default:
                return false;
        }
    }

// --- [5/100] getTokenAtPosition (Microsoft/vscode) ---

/**
 * Get the token whose text contains the position
 * @original_repo Microsoft/vscode
 * @original_name getTokenAtPosition
 */
function getTokenAtPosition(sourceFile, position, allowPositionInLeadingTrivia, includeEndPosition) {
    let current = sourceFile;
    outer: while (true) {
        // find the child that contains 'position'
        for (const child of current.getChildren()) {
            const start = allowPositionInLeadingTrivia ? child.getFullStart() : child.getStart(sourceFile, /*includeJsDoc*/ true);
            if (start > position) {
                // If this child begins after position, then all subsequent children will as well.
                break;
            }
            const end = child.getEnd();
            if (position < end || (position === end && (child.kind === ts.SyntaxKind.EndOfFileToken || includeEndPosition))) {
                current = child;
                continue outer;
            }
        }
        return current;
    }
}

// --- [6/100] handleDeletions (Microsoft/vscode) ---

/**
 * Ugly hack for gulp-tsb
 * @original_repo Microsoft/vscode
 * @original_name handleDeletions
 */
function handleDeletions() {
	return es.mapSync(f => {
		if (/\.ts$/.test(f.relative) && !f.contents) {
			f.contents = Buffer.from('');
			f.stat = { mtime: new Date() };
		}

		return f;
	});
}

// --- [7/100] uglifyWithCopyrights (Microsoft/vscode) ---

/**
 * Wrap around uglify and allow the preserveComments function
 * to have a file "context" to include our copyright only once per file.
 * @original_repo Microsoft/vscode
 * @original_name uglifyWithCopyrights
 */
function uglifyWithCopyrights() {
    const preserveComments = (f) => {
        return (_node, comment) => {
            const text = comment.value;
            const type = comment.type;
            if (/@minifier_do_not_preserve/.test(text)) {
                return false;
            }
            const isOurCopyright = IS_OUR_COPYRIGHT_REGEXP.test(text);
            if (isOurCopyright) {
                if (f.__hasOurCopyright) {
                    return false;
                }
                f.__hasOurCopyright = true;
                return true;
            }
            if ('comment2' === type) {
                // check for /*!. Note that text doesn't contain leading /*
                return (text.length > 0 && text[0] === '!') || /@preserve|license|@cc_on|copyright/i.test(text);
            }
            else if ('comment1' === type) {
                return /license|copyright/i.test(text);
            }
            return false;
        };
    };
    const minify = composer(uglifyes);
    const input = es.through();
    const output = input
        .pipe(flatmap((stream, f) => {
        return stream.pipe(minify({
            output: {
                comments: preserveComments(f),
                max_line_len: 1024
            }
        }));
    }));
    return es.duplex(input, output);
}

// --- [8/100] sequence (Microsoft/vscode) ---

/**
 * We're doing way too much stuff at once, with webpack et al. So much stuff
 * that while downloading extensions from the marketplace, node js doesn't get enough
 * stack frames to complete the download in under 2 minutes, at which point the
 * marketplace server cuts off the http request. So, we sequentialize the extensino tasks.
 * @original_repo Microsoft/vscode
 * @original_name sequence
 */
function sequence(streamProviders) {
    const result = es.through();
    function pop() {
        if (streamProviders.length === 0) {
            result.emit('end');
        }
        else {
            const fn = streamProviders.shift();
            fn()
                .on('end', function () { setTimeout(pop, 0); })
                .pipe(result, { end: false });
        }
    }
    pop();
    return result;
}

// --- [9/100] fixBadRegex (Microsoft/vscode) ---

/**
 * Workaround for https://github.com/Microsoft/vscode/issues/40279 and https://github.com/Microsoft/vscode-textmate/issues/59
 * @original_repo Microsoft/vscode
 * @original_name fixBadRegex
 */
function fixBadRegex(grammar) {
	const scopeResolution = grammar.repository['scope-resolution'];
	if (scopeResolution) {
		const match = scopeResolution.patterns[0].match;
		if (match === '(?i)([a-z_\\x{7f}-\\x{7fffffff}\\\\][a-z0-9_\\x{7f}-\\x{7fffffff}\\\\]*)(?=\\s*::)') {
			scopeResolution.patterns[0].match = '([A-Za-z_\\x{7f}-\\x{7fffffff}\\\\][A-Za-z0-9_\\x{7f}-\\x{7fffffff}\\\\]*)(?=\\s*::)';
			return;
		}
	}

	throw new Error(`fixBadRegex callback couldn't patch the regex. It may be obsolete`);
}

// --- [10/100] unknown (Microsoft/vscode) ---

/**
 * re-expose node's require function
 * @original_repo Microsoft/vscode
 * @original_name unknown
 */
function (what) {
                    moduleManager.getRecorder().record(33 /* NodeBeginNativeRequire */, what);
                    try {
                        return _nodeRequire_1(what);
                    }
                    finally {
                        moduleManager.getRecorder().record(34 /* NodeEndNativeRequire */, what);
                    }
                }

// --- [11/100] createTscCompileTask (Microsoft/vscode) ---

/**
 * #region monaco type checking
 * @original_repo Microsoft/vscode
 * @original_name createTscCompileTask
 */
function createTscCompileTask(watch) {
	return () => {
		const createReporter = require('./lib/reporter').createReporter;

		return new Promise((resolve, reject) => {
			const args = ['./node_modules/.bin/tsc', '-p', './src/tsconfig.monaco.json', '--noEmit'];
			if (watch) {
				args.push('-w');
			}
			const child = cp.spawn(`node`, args, {
				cwd: path.join(__dirname, '..'),
				// stdio: [null, 'pipe', 'inherit']
			});
			let errors = [];
			let reporter = createReporter();
			let report;
			// eslint-disable-next-line no-control-regex
			let magic = /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g; // https://stackoverflow.com/questions/25245716/remove-all-ansi-colors-styles-from-strings

			child.stdout.on('data', data => {
				let str = String(data);
				str = str.replace(magic, '').trim();
				if (str.indexOf('Starting compilation') >= 0 || str.indexOf('File change detected') >= 0) {
					errors.length = 0;
					report = reporter.end(false);

				} else if (str.indexOf('Compilation complete') >= 0) {
					report.end();

				} else if (str) {
					let match = /(.*\(\d+,\d+\): )(.*: )(.*)/.exec(str);
					if (match) {
						// trying to massage the message so that it matches the gulp-tsb error messages
						// e.g. src/vs/base/common/strings.ts(663,5): error TS2322: Type '1234' is not assignable to type 'string'.
						let fullpath = path.join(root, match[1]);
						let message = match[3];
						// @ts-ignore
						reporter(fullpath + message);
					} else {
						// @ts-ignore
						reporter(str);
					}
				}
			});
			child.on('exit', resolve);
			child.on('error', reject);
		});
	};
}

// --- [12/100] nls (Microsoft/vscode) ---

/**
 * Returns a stream containing the patched JavaScript and source maps.
 * @original_repo Microsoft/vscode
 * @original_name nls
 */
function nls() {
    const input = event_stream_1.through();
    const output = input.pipe(event_stream_1.through(function (f) {
        if (!f.sourceMap) {
            return this.emit('error', new Error(`File ${f.relative} does not have sourcemaps.`));
        }
        let source = f.sourceMap.sources[0];
        if (!source) {
            return this.emit('error', new Error(`File ${f.relative} does not have a source in the source map.`));
        }
        const root = f.sourceMap.sourceRoot;
        if (root) {
            source = path.join(root, source);
        }
        const typescript = f.sourceMap.sourcesContent[0];
        if (!typescript) {
            return this.emit('error', new Error(`File ${f.relative} does not have the original content in the source map.`));
        }
        nls.patchFiles(f, typescript).forEach(f => this.emit('data', f));
    }));
    return event_stream_1.duplex(input, output);
}

// --- [13/100] unknown (Microsoft/vscode) ---

/**
 * mac: Cmd-R, rest: Ctrl-R
 * @original_repo Microsoft/vscode
 * @original_name unknown
 */
function (e) {
		const key = extractKey(e);
		if (key === TOGGLE_DEV_TOOLS_KB || key === TOGGLE_DEV_TOOLS_KB_ALT) {
			ipc.send('vscode:toggleDevTools');
		} else if (key === RELOAD_KB) {
			ipc.send('vscode:reloadWindow');
		}
	}

// --- [14/100] bundle (Microsoft/vscode) ---

/**
 * Bundle `entryPoints` given config `config`.
 * @original_repo Microsoft/vscode
 * @original_name bundle
 */
function bundle(entryPoints, config, callback) {
    const entryPointsMap = {};
    entryPoints.forEach((module) => {
        entryPointsMap[module.name] = module;
    });
    const allMentionedModulesMap = {};
    entryPoints.forEach((module) => {
        allMentionedModulesMap[module.name] = true;
        (module.include || []).forEach(function (includedModule) {
            allMentionedModulesMap[includedModule] = true;
        });
        (module.exclude || []).forEach(function (excludedModule) {
            allMentionedModulesMap[excludedModule] = true;
        });
    });
    const code = require('fs').readFileSync(path.join(__dirname, '../../src/vs/loader.js'));
    const r = vm.runInThisContext('(function(require, module, exports) { ' + code + '\n});');
    const loaderModule = { exports: {} };
    r.call({}, require, loaderModule, loaderModule.exports);
    const loader = loaderModule.exports;
    config.isBuild = true;
    config.paths = config.paths || {};
    if (!config.paths['vs/nls']) {
        config.paths['vs/nls'] = 'out-build/vs/nls.build';
    }
    if (!config.paths['vs/css']) {
        config.paths['vs/css'] = 'out-build/vs/css.build';
    }
    loader.config(config);
    loader(['require'], (localRequire) => {
        const resolvePath = (path) => {
            const r = localRequire.toUrl(path);
            if (!/\.js/.test(r)) {
                return r + '.js';
            }
            return r;
        };
        for (const moduleId in entryPointsMap) {
            const entryPoint = entryPointsMap[moduleId];
            if (entryPoint.append) {
                entryPoint.append = entryPoint.append.map(resolvePath);
            }
            if (entryPoint.prepend) {
                entryPoint.prepend = entryPoint.prepend.map(resolvePath);
            }
        }
    });
    loader(Object.keys(allMentionedModulesMap), () => {
        const modules = loader.getBuildInfo();
        const partialResult = emitEntryPoints(modules, entryPointsMap);
        const cssInlinedResources = loader('vs/css').getInlinedResources();
        callback(null, {
            files: partialResult.files,
            cssInlinedResources: cssInlinedResources,
            bundleData: partialResult.bundleData
        });
    }, (err) => callback(err, null));
}

// --- [15/100] positionToOffset (Microsoft/vscode) ---

/**
 * Convert a position (line:col) to (offset) in string `str`
 * @original_repo Microsoft/vscode
 * @original_name positionToOffset
 */
function positionToOffset(str, desiredLine, desiredCol) {
    if (desiredLine === 1) {
        return desiredCol - 1;
    }
    let line = 1;
    let lastNewLineOffset = -1;
    do {
        if (desiredLine === line) {
            return lastNewLineOffset + 1 + desiredCol - 1;
        }
        lastNewLineOffset = str.indexOf('\n', lastNewLineOffset + 1);
        line++;
    } while (lastNewLineOffset >= 0);
    return -1;
}

// --- [16/100] visit (Microsoft/vscode) ---

/**
 * Return a set of reachable nodes in `graph` starting from `rootNodes`
 * @original_repo Microsoft/vscode
 * @original_name visit
 */
function visit(rootNodes, graph) {
    const result = {};
    const queue = rootNodes;
    rootNodes.forEach((node) => {
        result[node] = true;
    });
    while (queue.length > 0) {
        const el = queue.shift();
        const myEdges = graph[el] || [];
        myEdges.forEach((toNode) => {
            if (!result[toNode]) {
                result[toNode] = true;
                queue.push(toNode);
            }
        });
    }
    return result;
}

// --- [17/100] topologicalSort (Microsoft/vscode) ---

/**
 * Perform a topological sort on `graph`
 * @original_repo Microsoft/vscode
 * @original_name topologicalSort
 */
function topologicalSort(graph) {
    const allNodes = {}, outgoingEdgeCount = {}, inverseEdges = {};
    Object.keys(graph).forEach((fromNode) => {
        allNodes[fromNode] = true;
        outgoingEdgeCount[fromNode] = graph[fromNode].length;
        graph[fromNode].forEach((toNode) => {
            allNodes[toNode] = true;
            outgoingEdgeCount[toNode] = outgoingEdgeCount[toNode] || 0;
            inverseEdges[toNode] = inverseEdges[toNode] || [];
            inverseEdges[toNode].push(fromNode);
        });
    });
    // https://en.wikipedia.org/wiki/Topological_sorting
    const S = [], L = [];
    Object.keys(allNodes).forEach((node) => {
        if (outgoingEdgeCount[node] === 0) {
            delete outgoingEdgeCount[node];
            S.push(node);
        }
    });
    while (S.length > 0) {
        // Ensure the exact same order all the time with the same inputs
        S.sort();
        const n = S.shift();
        L.push(n);
        const myInverseEdges = inverseEdges[n] || [];
        myInverseEdges.forEach((m) => {
            outgoingEdgeCount[m]--;
            if (outgoingEdgeCount[m] === 0) {
                delete outgoingEdgeCount[m];
                S.push(m);
            }
        });
    }
    if (Object.keys(outgoingEdgeCount).length > 0) {
        throw new Error('Cannot do topological sort on cyclic graph, remaining nodes: ' + Object.keys(outgoingEdgeCount));
    }
    return L;
}

// --- [18/100] updateResource (Microsoft/vscode) ---

/**
 * The following link provides information about how Transifex handles updates of a resource file:
 * https://dev.befoolish.co/tx-docs/public/projects/updating-content#what-happens-when-you-update-files
 * @original_repo Microsoft/vscode
 * @original_name updateResource
 */
function updateResource(project, slug, xlfFile, apiHostname, credentials) {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify({ content: xlfFile.contents.toString() });
        const options = {
            hostname: apiHostname,
            path: `/api/2/project/${project}/resource/${slug}/content`,
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(data)
            },
            auth: credentials,
            method: 'PUT'
        };
        let request = https.request(options, (res) => {
            if (res.statusCode === 200) {
                res.setEncoding('utf8');
                let responseBuffer = '';
                res.on('data', function (chunk) {
                    responseBuffer += chunk;
                });
                res.on('end', () => {
                    const response = JSON.parse(responseBuffer);
                    log(`Resource ${project}/${slug} successfully updated on Transifex. Strings added: ${response.strings_added}, updated: ${response.strings_added}, deleted: ${response.strings_added}`);
                    resolve();
                });
            }
            else {
                reject(`Something went wrong in the request updating ${slug} in ${project}. ${res.statusCode}`);
            }
        });
        request.on('error', (err) => {
            reject(`Failed to update ${project}/${slug} on Transifex: ${err}`);
        });
        request.write(data);
        request.end();
    });
}

// --- [19/100] getVersion (Microsoft/vscode) ---

/**
 * Returns the sha1 commit version of a repository or undefined in case of failure.
 * @original_repo Microsoft/vscode
 * @original_name getVersion
 */
function getVersion(repo) {
    const git = path.join(repo, '.git');
    const headPath = path.join(git, 'HEAD');
    let head;
    try {
        head = fs.readFileSync(headPath, 'utf8').trim();
    }
    catch (e) {
        return undefined;
    }
    if (/^[0-9a-f]{40}$/i.test(head)) {
        return head;
    }
    const refMatch = /^ref: (.*)$/.exec(head);
    if (!refMatch) {
        return undefined;
    }
    const ref = refMatch[1];
    const refPath = path.join(git, ref);
    try {
        return fs.readFileSync(refPath, 'utf8').trim();
    }
    catch (e) {
        // noop
    }
    const packedRefsPath = path.join(git, 'packed-refs');
    let refsRaw;
    try {
        refsRaw = fs.readFileSync(packedRefsPath, 'utf8').trim();
    }
    catch (e) {
        return undefined;
    }
    const refsRegex = /^([0-9a-f]{40})\s+(.+)$/gm;
    let refsMatch;
    let refs = {};
    while (refsMatch = refsRegex.exec(refsRaw)) {
        refs[refsMatch[2]] = refsMatch[1];
    }
    return refs[ref];
}

// --- [20/100] pipeLoggingToParent (Microsoft/vscode) ---

/**
 * #region Helpers
 * @original_repo Microsoft/vscode
 * @original_name pipeLoggingToParent
 */
function pipeLoggingToParent() {
	const MAX_LENGTH = 100000;

	// Prevent circular stringify and convert arguments to real array
	function safeToArray(args) {
		const seen = [];
		const argsArray = [];

		let res;

		// Massage some arguments with special treatment
		if (args.length) {
			for (let i = 0; i < args.length; i++) {

				// Any argument of type 'undefined' needs to be specially treated because
				// JSON.stringify will simply ignore those. We replace them with the string
				// 'undefined' which is not 100% right, but good enough to be logged to console
				if (typeof args[i] === 'undefined') {
					args[i] = 'undefined';
				}

				// Any argument that is an Error will be changed to be just the error stack/message
				// itself because currently cannot serialize the error over entirely.
				else if (args[i] instanceof Error) {
					const errorObj = args[i];
					if (errorObj.stack) {
						args[i] = errorObj.stack;
					} else {
						args[i] = errorObj.toString();
					}
				}

				argsArray.push(args[i]);
			}
		}

		// Add the stack trace as payload if we are told so. We remove the message and the 2 top frames
		// to start the stacktrace where the console message was being written
		if (process.env.VSCODE_LOG_STACK === 'true') {
			const stack = new Error().stack;
			argsArray.push({ __$stack: stack.split('\n').slice(3).join('\n') });
		}

		try {
			res = JSON.stringify(argsArray, function (key, value) {

				// Objects get special treatment to prevent circles
				if (isObject(value) || Array.isArray(value)) {
					if (seen.indexOf(value) !== -1) {
						return '[Circular]';
					}

					seen.push(value);
				}

				return value;
			});
		} catch (error) {
			return 'Output omitted for an object that cannot be inspected (' + error.toString() + ')';
		}

		if (res && res.length > MAX_LENGTH) {
			return 'Output omitted for a large object that exceeds the limits';
		}

		return res;
	}

	function safeSend(arg) {
		try {
			process.send(arg);
		} catch (error) {
			// Can happen if the parent channel is closed meanwhile
		}
	}

	function isObject(obj) {
		return typeof obj === 'object'
			&& obj !== null
			&& !Array.isArray(obj)
			&& !(obj instanceof RegExp)
			&& !(obj instanceof Date);
	}

	// Pass console logging to the outside so that we have it in the main side if told so
	if (process.env.VERBOSE_LOGGING === 'true') {
		console.log = function () { safeSend({ type: '__$console', severity: 'log', arguments: safeToArray(arguments) }); };
		console.info = function () { safeSend({ type: '__$console', severity: 'log', arguments: safeToArray(arguments) }); };
		console.warn = function () { safeSend({ type: '__$console', severity: 'warn', arguments: safeToArray(arguments) }); };
	} else {
		console.log = function () { /* ignore */ };
		console.warn = function () { /* ignore */ };
		console.info = function () { /* ignore */ };
	}

	console.error = function () { safeSend({ type: '__$console', severity: 'error', arguments: safeToArray(arguments) }); };
}

// --- [21/100] safeToArray (Microsoft/vscode) ---

/**
 * Prevent circular stringify and convert arguments to real array
 * @original_repo Microsoft/vscode
 * @original_name safeToArray
 */
function safeToArray(args) {
		const seen = [];
		const argsArray = [];

		let res;

		// Massage some arguments with special treatment
		if (args.length) {
			for (let i = 0; i < args.length; i++) {

				// Any argument of type 'undefined' needs to be specially treated because
				// JSON.stringify will simply ignore those. We replace them with the string
				// 'undefined' which is not 100% right, but good enough to be logged to console
				if (typeof args[i] === 'undefined') {
					args[i] = 'undefined';
				}

				// Any argument that is an Error will be changed to be just the error stack/message
				// itself because currently cannot serialize the error over entirely.
				else if (args[i] instanceof Error) {
					const errorObj = args[i];
					if (errorObj.stack) {
						args[i] = errorObj.stack;
					} else {
						args[i] = errorObj.toString();
					}
				}

				argsArray.push(args[i]);
			}
		}

		// Add the stack trace as payload if we are told so. We remove the message and the 2 top frames
		// to start the stacktrace where the console message was being written
		if (process.env.VSCODE_LOG_STACK === 'true') {
			const stack = new Error().stack;
			argsArray.push({ __$stack: stack.split('\n').slice(3).join('\n') });
		}

		try {
			res = JSON.stringify(argsArray, function (key, value) {

				// Objects get special treatment to prevent circles
				if (isObject(value) || Array.isArray(value)) {
					if (seen.indexOf(value) !== -1) {
						return '[Circular]';
					}

					seen.push(value);
				}

				return value;
			});
		} catch (error) {
			return 'Output omitted for an object that cannot be inspected (' + error.toString() + ')';
		}

		if (res && res.length > MAX_LENGTH) {
			return 'Output omitted for a large object that exceeds the limits';
		}

		return res;
	}

// --- [22/100] showPartsSplash (Microsoft/vscode) ---

/**
 * // configuration: IWindowConfiguration
 * @param {{
 * partsSplashPath?: string,
 * highContrast?: boolean,
 * extensionDevelopmentPath?: string | string[],
 * folderUri?: object,
 * workspace?: object
 * }} configuration
 * @original_repo Microsoft/vscode
 * @original_name showPartsSplash
 */
function showPartsSplash(configuration) {
	perf.mark('willShowPartsSplash');

	let data;
	if (typeof configuration.partsSplashPath === 'string') {
		try {
			data = JSON.parse(require('fs').readFileSync(configuration.partsSplashPath, 'utf8'));
		} catch (e) {
			// ignore
		}
	}

	// high contrast mode has been turned on from the outside, e.g OS -> ignore stored colors and layouts
	if (data && configuration.highContrast && data.baseTheme !== 'hc-black') {
		data = undefined;
	}

	// developing an extension -> ignore stored layouts
	if (data && configuration.extensionDevelopmentPath) {
		data.layoutInfo = undefined;
	}

	// minimal color configuration (works with or without persisted data)
	const baseTheme = data ? data.baseTheme : configuration.highContrast ? 'hc-black' : 'vs-dark';
	const shellBackground = data ? data.colorInfo.editorBackground : configuration.highContrast ? '#000000' : '#1E1E1E';
	const shellForeground = data ? data.colorInfo.foreground : configuration.highContrast ? '#FFFFFF' : '#CCCCCC';
	const style = document.createElement('style');
	style.className = 'initialShellColors';
	document.head.appendChild(style);
	document.body.className = `monaco-shell ${baseTheme}`;
	style.innerHTML = `.monaco-shell { background-color: ${shellBackground}; color: ${shellForeground}; }`;

	if (data && data.layoutInfo) {
		// restore parts if possible (we might not always store layout info)
		const { id, layoutInfo, colorInfo } = data;
		const splash = document.createElement('div');
		splash.id = id;

		// ensure there is enough space
		layoutInfo.sideBarWidth = Math.min(layoutInfo.sideBarWidth, window.innerWidth - (layoutInfo.activityBarWidth + layoutInfo.editorPartMinWidth));

		if (configuration.folderUri || configuration.workspace) {
			// folder or workspace -> status bar color, sidebar
			splash.innerHTML = `
			<div style="position: absolute; width: 100%; left: 0; top: 0; height: ${layoutInfo.titleBarHeight}px; background-color: ${colorInfo.titleBarBackground}; -webkit-app-region: drag;"></div>
			<div style="position: absolute; height: calc(100% - ${layoutInfo.titleBarHeight}px); top: ${layoutInfo.titleBarHeight}px; ${layoutInfo.sideBarSide}: 0; width: ${layoutInfo.activityBarWidth}px; background-color: ${colorInfo.activityBarBackground};"></div>
			<div style="position: absolute; height: calc(100% - ${layoutInfo.titleBarHeight}px); top: ${layoutInfo.titleBarHeight}px; ${layoutInfo.sideBarSide}: ${layoutInfo.activityBarWidth}px; width: ${layoutInfo.sideBarWidth}px; background-color: ${colorInfo.sideBarBackground};"></div>
			<div style="position: absolute; width: 100%; bottom: 0; left: 0; height: ${layoutInfo.statusBarHeight}px; background-color: ${colorInfo.statusBarBackground};"></div>
			`;
		} else {
			// empty -> speical status bar color, no sidebar
			splash.innerHTML = `
			<div style="position: absolute; width: 100%; left: 0; top: 0; height: ${layoutInfo.titleBarHeight}px; background-color: ${colorInfo.titleBarBackground}; -webkit-app-region: drag;"></div>
			<div style="position: absolute; height: calc(100% - ${layoutInfo.titleBarHeight}px); top: ${layoutInfo.titleBarHeight}px; ${layoutInfo.sideBarSide}: 0; width: ${layoutInfo.activityBarWidth}px; background-color: ${colorInfo.activityBarBackground};"></div>
			<div style="position: absolute; width: 100%; bottom: 0; left: 0; height: ${layoutInfo.statusBarHeight}px; background-color: ${colorInfo.statusBarNoFolderBackground};"></div>
			`;
		}
		document.body.appendChild(splash);
	}

	perf.mark('didShowPartsSplash');
}

// --- [23/100] computeChecksums (Microsoft/vscode) ---

/**
 * Compute checksums for some files.
 * 
 * @param {string} out The out folder to read the file from.
 * @param {string[]} filenames The paths to compute a checksum for.
 * @return {Object} A map of paths to checksums.
 * @original_repo Microsoft/vscode
 * @original_name computeChecksums
 */
function computeChecksums(out, filenames) {
	var result = {};
	filenames.forEach(function (filename) {
		var fullPath = path.join(process.cwd(), out, filename);
		result[filename] = computeChecksum(fullPath);
	});
	return result;
}

// --- [24/100] computeChecksum (Microsoft/vscode) ---

/**
 * Compute checksum for a file.
 * 
 * @param {string} filename The absolute path to a filename.
 * @return {string} The checksum for `filename`.
 * @original_repo Microsoft/vscode
 * @original_name computeChecksum
 */
function computeChecksum(filename) {
	var contents = fs.readFileSync(filename);

	var hash = crypto
		.createHash('md5')
		.update(contents)
		.digest('base64')
		.replace(/=+$/, '');

	return hash;
}

// --- [25/100] configureCommandlineSwitches (Microsoft/vscode) ---

/**
 * @typedef {import('minimist').ParsedArgs} ParsedArgs
 * 
 * @param {ParsedArgs} cliArgs
 * @param {{ jsFlags: () => string }} nodeCachedDataDir
 * @original_repo Microsoft/vscode
 * @original_name configureCommandlineSwitches
 */
function configureCommandlineSwitches(cliArgs, nodeCachedDataDir) {

	// Force pre-Chrome-60 color profile handling (for https://github.com/Microsoft/vscode/issues/51791)
	app.commandLine.appendSwitch('disable-color-correct-rendering');

	// Support JS Flags
	const jsFlags = resolveJSFlags(cliArgs, nodeCachedDataDir.jsFlags());
	if (jsFlags) {
		app.commandLine.appendSwitch('--js-flags', jsFlags);
	}

	// Disable smooth scrolling for Webviews
	if (cliArgs['disable-smooth-scrolling']) {
		app.commandLine.appendSwitch('disable-smooth-scrolling');
	}
}

// --- [26/100] getUserDataPath (Microsoft/vscode) ---

/**
 * @param {ParsedArgs} cliArgs
 * 
 * @returns {string}
 * @original_repo Microsoft/vscode
 * @original_name getUserDataPath
 */
function getUserDataPath(cliArgs) {
	if (portable.isPortable) {
		return path.join(portable.portableDataPath, 'user-data');
	}

	return path.resolve(cliArgs['user-data-dir'] || paths.getDefaultUserDataPath(process.platform));
}

// --- [27/100] stripComments (Microsoft/vscode) ---

/**
 * #region NLS Support
 * @param {string} content
 * @returns {string}
 * @original_repo Microsoft/vscode
 * @original_name stripComments
 */
function stripComments(content) {
	const regexp = /("(?:[^\\"]*(?:\\.)?)*")|('(?:[^\\']*(?:\\.)?)*')|(\/\*(?:\r?\n|.)*?\*\/)|(\/{2,}.*?(?:(?:\r?\n)|$))/g;

	return content.replace(regexp, function (match, m1, m2, m3, m4) {
		// Only one of m1, m2, m3, m4 matches
		if (m3) {
			// A block comment. Replace with nothing
			return '';
		} else if (m4) {
			// A line comment. If it ends in \r?\n then keep it.
			const length_1 = m4.length;
			if (length_1 > 2 && m4[length_1 - 1] === '\n') {
				return m4[length_1 - 2] === '\r' ? '\r\n' : '\n';
			}
			else {
				return '';
			}
		} else {
			// We match a string
			return match;
		}
	});
}

// --- [28/100] getUserDefinedLocale (Microsoft/vscode) ---

/**
 * Language tags are case insensitive however an amd loader is case sensitive To make this work on case preserving & insensitive FS we do the following: the language bundles have lower case language tags and we always lower case the locale we receive from the user or OS.
 * @returns {Promise<string>}
 * @original_repo Microsoft/vscode
 * @original_name getUserDefinedLocale
 */
function getUserDefinedLocale() {
	const locale = args['locale'];
	if (locale) {
		return Promise.resolve(locale.toLowerCase());
	}

	const localeConfig = path.join(userDataPath, 'User', 'locale.json');
	return bootstrap.readFile(localeConfig).then(content => {
		content = stripComments(content);
		try {
			const value = JSON.parse(content).locale;
			return value && typeof value === 'string' ? value.toLowerCase() : undefined;
		} catch (e) {
			return undefined;
		}
	}, () => {
		return undefined;
	});
}

// --- [29/100] getUID (twbs/bootstrap) ---

/**
 * --------------------------------------------------------------------------
 * Public Util Api
 * --------------------------------------------------------------------------
 * @original_repo twbs/bootstrap
 * @original_name getUID
 */
function getUID(prefix) {
  do {
    // eslint-disable-next-line no-bitwise
    prefix += ~~(Math.random() * MAX_UID); // "~~" acts like a faster Math.floor() here
  } while (document.getElementById(prefix));

  return prefix;
}

// --- [30/100] normalizeData (twbs/bootstrap) ---

/**
 * --------------------------------------------------------------------------
 * Bootstrap (v4.3.1): dom/manipulator.js
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * --------------------------------------------------------------------------
 * @original_repo twbs/bootstrap
 * @original_name normalizeData
 */
function normalizeData(val) {
  if (val === 'true') {
    return true;
  }

  if (val === 'false') {
    return false;
  }

  if (val === Number(val).toString()) {
    return Number(val);
  }

  if (val === '' || val === 'null') {
    return null;
  }

  return val;
}

// --- [31/100] $TypedArray$ (angular/angular) ---

/**
 * 5 The Typed Array View Types
 * @original_repo angular/angular
 * @original_name $TypedArray$
 */
function $TypedArray$() {

      // %TypedArray% ( length )
      if (!arguments.length || typeof arguments[0] !== 'object') {
        return (function(length) {
          length = ToInt32(length);
          if (length < 0) throw RangeError('length is not a small enough positive integer.');
          Object.defineProperty(this, 'length', {value: length});
          Object.defineProperty(this, 'byteLength', {value: length * this.BYTES_PER_ELEMENT});
          Object.defineProperty(this, 'buffer', {value: new ArrayBuffer(this.byteLength)});
          Object.defineProperty(this, 'byteOffset', {value: 0});

        }).apply(this, arguments);
      }

      // %TypedArray% ( typedArray )
      if (arguments.length >= 1 &&
        Type(arguments[0]) === 'object' &&
        arguments[0] instanceof $TypedArray$) {
        return (function(typedArray){
          if (this.constructor !== typedArray.constructor) throw TypeError();

          var byteLength = typedArray.length * this.BYTES_PER_ELEMENT;
          Object.defineProperty(this, 'buffer', {value: new ArrayBuffer(byteLength)});
          Object.defineProperty(this, 'byteLength', {value: byteLength});
          Object.defineProperty(this, 'byteOffset', {value: 0});
          Object.defineProperty(this, 'length', {value: typedArray.length});

          for (var i = 0; i < this.length; i += 1)
            this._setter(i, typedArray._getter(i));

        }).apply(this, arguments);
      }

      // %TypedArray% ( array )
      if (arguments.length >= 1 &&
        Type(arguments[0]) === 'object' &&
        !(arguments[0] instanceof $TypedArray$) &&
        !(arguments[0] instanceof ArrayBuffer || Class(arguments[0]) === 'ArrayBuffer')) {
        return (function(array) {

          var byteLength = array.length * this.BYTES_PER_ELEMENT;
          Object.defineProperty(this, 'buffer', {value: new ArrayBuffer(byteLength)});
          Object.defineProperty(this, 'byteLength', {value: byteLength});
          Object.defineProperty(this, 'byteOffset', {value: 0});
          Object.defineProperty(this, 'length', {value: array.length});

          for (var i = 0; i < this.length; i += 1) {
            var s = array[i];
            this._setter(i, Number(s));
          }
        }).apply(this, arguments);
      }

      // %TypedArray% ( buffer, byteOffset=0, length=undefined )
      if (arguments.length >= 1 &&
        Type(arguments[0]) === 'object' &&
        (arguments[0] instanceof ArrayBuffer || Class(arguments[0]) === 'ArrayBuffer')) {
        return (function(buffer, byteOffset, length) {

          byteOffset = ToUint32(byteOffset);
          if (byteOffset > buffer.byteLength)
            throw RangeError('byteOffset out of range');

          // The given byteOffset must be a multiple of the element
          // size of the specific type, otherwise an exception is raised.
          if (byteOffset % this.BYTES_PER_ELEMENT)
            throw RangeError('buffer length minus the byteOffset is not a multiple of the element size.');

          if (length === undefined) {
            var byteLength = buffer.byteLength - byteOffset;
            if (byteLength % this.BYTES_PER_ELEMENT)
              throw RangeError('length of buffer minus byteOffset not a multiple of the element size');
            length = byteLength / this.BYTES_PER_ELEMENT;

          } else {
            length = ToUint32(length);
            byteLength = length * this.BYTES_PER_ELEMENT;
          }

          if ((byteOffset + byteLength) > buffer.byteLength)
            throw RangeError('byteOffset and length reference an area beyond the end of the buffer');

          Object.defineProperty(this, 'buffer', {value: buffer});
          Object.defineProperty(this, 'byteLength', {value: byteLength});
          Object.defineProperty(this, 'byteOffset', {value: byteOffset});
          Object.defineProperty(this, 'length', {value: length});

        }).apply(this, arguments);
      }

      // %TypedArray% ( all other argument combinations )
      throw TypeError();
    }

// --- [32/100] makeTypedArray (angular/angular) ---

/**
 * %TypedArray%.prototype.toLocaleString ( ) %TypedArray%.prototype.toString ( ) %TypedArray%.prototype.values ( ) %TypedArray%.prototype [ @@iterator ] ( ) get %TypedArray%.prototype [ @@toStringTag ] -- defined in es6.js to shim browsers w/ native TypedArrays
 * @original_repo angular/angular
 * @original_name makeTypedArray
 */
function makeTypedArray(elementSize, pack, unpack) {
      // Each TypedArray type requires a distinct constructor instance with
      // identical logic, which this produces.
      var TypedArray = function() {
        Object.defineProperty(this, 'constructor', {value: TypedArray});
        $TypedArray$.apply(this, arguments);
        makeArrayAccessors(this);
      };
      if ('__proto__' in TypedArray) {
        TypedArray.__proto__ = $TypedArray$;
      } else {
        TypedArray.from = $TypedArray$.from;
        TypedArray.of = $TypedArray$.of;
      }

      TypedArray.BYTES_PER_ELEMENT = elementSize;

      var TypedArrayPrototype = function() {};
      TypedArrayPrototype.prototype = $TypedArrayPrototype$;

      TypedArray.prototype = new TypedArrayPrototype();

      Object.defineProperty(TypedArray.prototype, 'BYTES_PER_ELEMENT', {value: elementSize});
      Object.defineProperty(TypedArray.prototype, '_pack', {value: pack});
      Object.defineProperty(TypedArray.prototype, '_unpack', {value: unpack});

      return TypedArray;
    }

// --- [33/100] DataView (angular/angular) ---

/**
 * DataView(buffer, byteOffset=0, byteLength=undefined) WebIDL: Constructor(ArrayBuffer buffer, optional unsigned long byteOffset, optional unsigned long byteLength)
 * @original_repo angular/angular
 * @original_name DataView
 */
function DataView(buffer, byteOffset, byteLength) {
      if (!(buffer instanceof ArrayBuffer || Class(buffer) === 'ArrayBuffer')) throw TypeError();

      byteOffset = ToUint32(byteOffset);
      if (byteOffset > buffer.byteLength)
        throw RangeError('byteOffset out of range');

      if (byteLength === undefined)
        byteLength = buffer.byteLength - byteOffset;
      else
        byteLength = ToUint32(byteLength);

      if ((byteOffset + byteLength) > buffer.byteLength)
        throw RangeError('byteOffset and length reference an area beyond the end of the buffer');

      Object.defineProperty(this, 'buffer', {value: buffer});
      Object.defineProperty(this, 'byteLength', {value: byteLength});
      Object.defineProperty(this, 'byteOffset', {value: byteOffset});
    }

// --- [34/100] checkEnvironment (angular/angular) ---

/**
 * Helpers
 * @original_repo angular/angular
 * @original_name checkEnvironment
 */
function checkEnvironment(expected) {
  exec('yarn --version', function(yarnErr, yarnStdout) {
    var actualNodeVersion = process.version;
    var actualYarnVersion = !yarnErr && semver.clean(yarnStdout);
    var issues = [];

    // Check Node version.
    if (!semver.satisfies(actualNodeVersion, expected.nodeVersion)) {
      issues.push(
          'You are running an unsupported Node version. Expected: ' + expected.nodeVersion +
          ' Found: ' + actualNodeVersion + '. Use nvm to update your Node version.');
    }

    // Check yarn version.
    if (yarnErr) {
      issues.push(
          'You don\'t have yarn globally installed. This is required if you want to work on this ' +
          'project. Installation instructions: https://yarnpkg.com/lang/en/docs/install/');
    } else if (!semver.satisfies(actualYarnVersion, expected.yarnVersion)) {
      issues.push(
          'You are running an unsupported yarn version. Expected: ' + expected.yarnVersion +
          ' Found: ' + actualYarnVersion + '. For instructions see:' +
          ' https://yarnpkg.com/lang/en/docs/install/');
    }

    reportIssues(issues);
  });
}

// --- [35/100] listify (angular/angular) ---

/**
 * Convert an array of strings in to a human list - e.g separated by commas and the word `and`.
 * @param {string[]} values The strings to convert to a list
 * @original_repo angular/angular
 * @original_name listify
 */
function listify(values) {
  if (values.length <= 1) return values;
  const last = values[values.length - 1];
  const rest = values.slice(0, values.length - 1);
  return [rest.join(', '), last].join(' and ');
}

// --- [36/100] tokenize (angular/angular) ---

/**
 * If the heading contains a name starting with ng, e.g. "ngController", then add the name without the ng to the text, e.g. "controller".
 * @original_repo angular/angular
 * @original_name tokenize
 */
function tokenize(text) {
  const rawTokens = text.split(/[\s\/]+/mg);
  const tokens = [];
  rawTokens.forEach(token => {
    // Strip off unwanted trivial characters
    token = token
        .trim()
        .replace(/^[_\-"'`({[<$*)}\]>.]+/, '')
        .replace(/[_\-"'`({[<$*)}\]>.]+$/, '');
    // Ignore tokens that contain weird characters
    if (/^[\w.\-]+$/.test(token)) {
      tokens.push(token.toLowerCase());
      const ngTokenMatch = /^[nN]g([A-Z]\w*)/.exec(token);
      if (ngTokenMatch) {
        tokens.push(ngTokenMatch[1].toLowerCase());
      }
    }
  });
  return tokens;
}

// --- [37/100] mockTimeout (angular/angular) ---

/**
 * setTimeout/clearTimeout mocking, mostly stolen from angular-mocks.js
 * @original_repo angular/angular
 * @original_name mockTimeout
 */
function mockTimeout() {
  var events = [];
  var id = 0;
  var now = 0;

  return {
    mocks: {setTimeout: mockSetTimeout, clearTimeout: mockClearTimeout},
    flush: flush, get pending() { return events.length; }
  };

  function mockSetTimeout(fn, delay) {
    delay = delay || 0;
    events.push({time: now + delay, fn: fn, id: id});
    events.sort(function(a, b) { return a.time - b.time; });
    return id++;
  }

  function mockClearTimeout(id) {
    for (var i = 0; i < events.length; ++i) {
      if (events[i].id === id) {
        events.splice(i, 1);
        break;
      }
    }
  }

  function flush(delay) {
    if (delay !== undefined)
      now += delay;
    else if (events.length)
      now = events[events.length - 1].time;
    else
      throw new Error('No timer events registered');

    while (events.length && events[0].time <= now) {
      events.shift().fn();
    }
  }
}

// --- [38/100] _main (angular/angular) ---

/**
 * Helpers
 * @original_repo angular/angular
 * @original_name _main
 */
function _main(args) {
  triggerWebhook(...args).
    then(({statusCode, responseText}) => (200 <= statusCode && statusCode < 400) ?
      console.log(`Status: ${statusCode}\n${responseText}`) :
      Promise.reject(new Error(`Request failed (status: ${statusCode}): ${responseText}`))).
    catch(err => {
      console.error(err);
      process.exit(1);
    });
}

// --- [39/100] _main (angular/angular) ---

/**
 * Functions - Definitions
 * @original_repo angular/angular
 * @original_name _main
 */
function _main() {
  const contributors = JSON.parse(readFileSync(CONTRIBUTORS_PATH, 'utf8'));
  const expectedImages = Object.keys(contributors)
      .filter(key => !!contributors[key].picture)
      .map(key => join(IMAGES_DIR, contributors[key].picture));
  const missingImages = expectedImages.filter(path => !existsSync(path));

  if (missingImages.length > 0) {
    throw new Error(
        'The following pictures are referenced in \'contributors.json\' but do not exist:' +
        missingImages.map(path => `\n  - ${path}`).join(''));
  }
}

// --- [40/100] _main (angular/angular) ---

/**
 * Functions - Definitions
 * @original_repo angular/angular
 * @original_name _main
 */
function _main() {
  const {guides: acGuidePaths, images: acGuideImagesPaths, examples: acExamplePaths} = getPathsFromAioContent();
  const {guides: coGuidePaths, images: coGuideImagesPaths, examples: coExamplePaths} = getPathsFromCodeowners();

  const guidesDiff = arrayDiff(acGuidePaths, coGuidePaths);
  const imagesDiff = arrayDiff(acGuideImagesPaths, coGuideImagesPaths);
  const examplesDiff = arrayDiff(acExamplePaths, coExamplePaths);
  const hasDiff = !!(guidesDiff.diffCount || imagesDiff.diffCount || examplesDiff.diffCount);

  if (hasDiff) {
    const expectedGuidesSrc = path.relative(PROJECT_ROOT_DIR, AIO_GUIDES_DIR);
    const expectedImagesSrc = path.relative(PROJECT_ROOT_DIR, AIO_GUIDE_IMAGES_DIR);
    const expectedExamplesSrc = path.relative(PROJECT_ROOT_DIR, AIO_GUIDE_EXAMPLES_DIR);
    const actualSrc = path.relative(PROJECT_ROOT_DIR, CODEOWNERS_PATH);

    reportDiff(guidesDiff, expectedGuidesSrc, actualSrc);
    reportDiff(imagesDiff, expectedImagesSrc, actualSrc);
    reportDiff(examplesDiff, expectedExamplesSrc, actualSrc);
  }

  process.exit(hasDiff ? 1 : 0);
}

// --- [41/100] readProperty (angular/angular) ---

/**
 * Search deeply into an object via a collection of property segments, starting at the
 * indexed segment.
 * 
 * E.g. if `obj = { a: { b: { c: 10 }}}` then
 * `readProperty(obj, ['a', 'b', 'c'], 0)` will return true;
 * but
 * `readProperty(obj, ['a', 'd'], 0)` will return false;
 * @original_repo angular/angular
 * @original_name readProperty
 */
function readProperty(obj, propertySegments, index) {
  const value = obj[propertySegments[index]];
  return !!value && (index === propertySegments.length - 1 || readProperty(value, propertySegments, index + 1));
}

// --- [42/100] generateLocale (angular/angular) ---

/**
 * Generate file that contains basic locale data
 * @original_repo angular/angular
 * @original_name generateLocale
 */
function generateLocale(locale, localeData, baseCurrencies) {
  // [ localeId, dateTime, number, currency, pluralCase ]
  let data = stringify([
    locale,
    ...getDateTimeTranslations(localeData),
    ...getDateTimeSettings(localeData),
    ...getNumberSettings(localeData),
    ...getCurrencySettings(locale, localeData),
    generateLocaleCurrencies(localeData, baseCurrencies)
  ], true)
  // We remove "undefined" added by spreading arrays when there is no value
    .replace(/undefined/g, 'u');

  // adding plural function after, because we don't want it as a string
  data = data.substring(0, data.lastIndexOf(']')) + `, plural]`;

  return `${HEADER}
const u = undefined;

${getPluralFunction(locale)}

export default ${data};
`;
}

// --- [43/100] generateLocaleExtra (angular/angular) ---

/**
 * Generate a file that contains extra data (for now: day period rules, and extended day period data)
 * @original_repo angular/angular
 * @original_name generateLocaleExtra
 */
function generateLocaleExtra(locale, localeData) {
  const dayPeriods = getDayPeriodsNoAmPm(localeData);
  const dayPeriodRules = getDayPeriodRules(localeData);

  let dayPeriodsSupplemental = [];

  if (Object.keys(dayPeriods.format.narrow).length) {
    const keys = Object.keys(dayPeriods.format.narrow);

    if (keys.length !== Object.keys(dayPeriodRules).length) {
      throw new Error(`Error: locale ${locale} has not the correct number of day period rules`);
    }

    const dayPeriodsFormat = removeDuplicates([
      objectValues(dayPeriods.format.narrow),
      objectValues(dayPeriods.format.abbreviated),
      objectValues(dayPeriods.format.wide)
    ]);

    const dayPeriodsStandalone = removeDuplicates([
      objectValues(dayPeriods['stand-alone'].narrow),
      objectValues(dayPeriods['stand-alone'].abbreviated),
      objectValues(dayPeriods['stand-alone'].wide)
    ]);

    const rules = keys.map(key => dayPeriodRules[key]);

    dayPeriodsSupplemental = [...removeDuplicates([dayPeriodsFormat, dayPeriodsStandalone]), rules];
  }

  return `${HEADER}
const u = undefined;

export default ${stringify(dayPeriodsSupplemental).replace(/undefined/g, 'u')};
`;
}

// --- [44/100] generateBaseCurrencies (angular/angular) ---

/**
 * Generate a list of currencies to be used as a based for other currencies
 * e.g.: {'ARS': [, '$'], 'AUD': ['A$', '$'], ...}
 * @original_repo angular/angular
 * @original_name generateBaseCurrencies
 */
function generateBaseCurrencies(localeData, addDigits) {
  const currenciesData = localeData.main('numbers/currencies');
  const fractions = new cldrJs('en').get(`supplemental/currencyData/fractions`);
  const currencies = {};
  Object.keys(currenciesData).forEach(key => {
    let symbolsArray = [];
    const symbol = currenciesData[key].symbol;
    const symbolNarrow = currenciesData[key]['symbol-alt-narrow'];
    if (symbol && symbol !== key) {
      symbolsArray.push(symbol);
    }
    if (symbolNarrow && symbolNarrow !== symbol) {
      if (symbolsArray.length > 0) {
        symbolsArray.push(symbolNarrow);
      } else {
        symbolsArray = [undefined, symbolNarrow];
      }
    }
    if (addDigits && fractions[key] && fractions[key]['_digits']) {
      const digits = parseInt(fractions[key]['_digits'], 10);
      if (symbolsArray.length === 2) {
        symbolsArray.push(digits);
      } else if (symbolsArray.length === 1) {
        symbolsArray = [...symbolsArray, undefined, digits];
      } else {
        symbolsArray = [undefined, undefined, digits];
      }
    }
    if (symbolsArray.length > 0) {
      currencies[key] = symbolsArray;
    }
  });
  return currencies;
}

// --- [45/100] generateLocaleCurrencies (angular/angular) ---

/**
 * To minimize the file even more, we only output the differences compared to the base currency
 * @original_repo angular/angular
 * @original_name generateLocaleCurrencies
 */
function generateLocaleCurrencies(localeData, baseCurrencies) {
  const currenciesData = localeData.main('numbers/currencies');
  const currencies = {};
  Object.keys(currenciesData).forEach(code => {
    let symbolsArray = [];
    const symbol = currenciesData[code].symbol;
    const symbolNarrow = currenciesData[code]['symbol-alt-narrow'];
    if (symbol && symbol !== code) {
      symbolsArray.push(symbol);
    }
    if (symbolNarrow && symbolNarrow !== symbol) {
      if (symbolsArray.length > 0) {
        symbolsArray.push(symbolNarrow);
      } else {
        symbolsArray = [undefined, symbolNarrow];
      }
    }

    // if locale data are different, set the value
    if ((baseCurrencies[code] || []).toString() !== symbolsArray.toString()) {
      currencies[code] = symbolsArray;
    }
  });
  return currencies;
}

// --- [46/100] getDayPeriods (angular/angular) ---

/**
 * Returns data for the chosen day periods
 * @returns {format: {narrow / abbreviated / wide: [...]}, stand-alone: {narrow / abbreviated / wide: [...]}}
 * @original_repo angular/angular
 * @original_name getDayPeriods
 */
function getDayPeriods(localeData, dayPeriodsList) {
  const dayPeriods = localeData.main(`dates/calendars/gregorian/dayPeriods`);
  const result = {};
  // cleaning up unused keys
  Object.keys(dayPeriods).forEach(key1 => {          // format / stand-alone
    result[key1] = {};
    Object.keys(dayPeriods[key1]).forEach(key2 => {  // narrow / abbreviated / wide
      result[key1][key2] = {};
      Object.keys(dayPeriods[key1][key2]).forEach(key3 => {
        if (dayPeriodsList.indexOf(key3) !== -1) {
          result[key1][key2][key3] = dayPeriods[key1][key2][key3];
        }
      });
    });
  });

  return result;
}

// --- [47/100] getDateTimeTranslations (angular/angular) ---

/**
 * Returns date-related translations for a locale
 * @returns [ dayPeriodsFormat, dayPeriodsStandalone, daysFormat, dayStandalone, monthsFormat, monthsStandalone, eras ]
 * each value: [ narrow, abbreviated, wide, short? ]
 * @original_repo angular/angular
 * @original_name getDateTimeTranslations
 */
function getDateTimeTranslations(localeData) {
  const dayNames = localeData.main(`dates/calendars/gregorian/days`);
  const monthNames = localeData.main(`dates/calendars/gregorian/months`);
  const erasNames = localeData.main(`dates/calendars/gregorian/eras`);
  const dayPeriods = getDayPeriodsAmPm(localeData);

  const dayPeriodsFormat = removeDuplicates([
    objectValues(dayPeriods.format.narrow),
    objectValues(dayPeriods.format.abbreviated),
    objectValues(dayPeriods.format.wide)
  ]);

  const dayPeriodsStandalone = removeDuplicates([
    objectValues(dayPeriods['stand-alone'].narrow),
    objectValues(dayPeriods['stand-alone'].abbreviated),
    objectValues(dayPeriods['stand-alone'].wide)
  ]);

  const daysFormat = removeDuplicates([
    objectValues(dayNames.format.narrow),
    objectValues(dayNames.format.abbreviated),
    objectValues(dayNames.format.wide),
    objectValues(dayNames.format.short)
  ]);

  const daysStandalone = removeDuplicates([
    objectValues(dayNames['stand-alone'].narrow),
    objectValues(dayNames['stand-alone'].abbreviated),
    objectValues(dayNames['stand-alone'].wide),
    objectValues(dayNames['stand-alone'].short)
  ]);

  const monthsFormat = removeDuplicates([
    objectValues(monthNames.format.narrow),
    objectValues(monthNames.format.abbreviated),
    objectValues(monthNames.format.wide)
  ]);

  const monthsStandalone = removeDuplicates([
    objectValues(monthNames['stand-alone'].narrow),
    objectValues(monthNames['stand-alone'].abbreviated),
    objectValues(monthNames['stand-alone'].wide)
  ]);

  const eras = removeDuplicates([
    [erasNames.eraNarrow['0'], erasNames.eraNarrow['1']],
    [erasNames.eraAbbr['0'], erasNames.eraAbbr['1']],
    [erasNames.eraNames['0'], erasNames.eraNames['1']]
  ]);

  const dateTimeTranslations = [
    ...removeDuplicates([dayPeriodsFormat, dayPeriodsStandalone]),
    ...removeDuplicates([daysFormat, daysStandalone]),
    ...removeDuplicates([monthsFormat, monthsStandalone]),
    eras
  ];

  return dateTimeTranslations;
}

// --- [48/100] getDateTimeFormats (angular/angular) ---

/**
 * Returns date, time and dateTime formats for a locale
 * @returns [dateFormats, timeFormats, dateTimeFormats]
 * each format: [ short, medium, long, full ]
 * @original_repo angular/angular
 * @original_name getDateTimeFormats
 */
function getDateTimeFormats(localeData) {
  function getFormats(data) {
    return removeDuplicates([
      data.short._value || data.short,
      data.medium._value || data.medium,
      data.long._value || data.long,
      data.full._value || data.full
    ]);
  }

  const dateFormats = localeData.main('dates/calendars/gregorian/dateFormats');
  const timeFormats = localeData.main('dates/calendars/gregorian/timeFormats');
  const dateTimeFormats = localeData.main('dates/calendars/gregorian/dateTimeFormats');

  return [
    getFormats(dateFormats),
    getFormats(timeFormats),
    getFormats(dateTimeFormats)
  ];
}

// --- [49/100] getDayPeriodRules (angular/angular) ---

/**
 * Returns day period rules for a locale
 * @returns string[]
 * @original_repo angular/angular
 * @original_name getDayPeriodRules
 */
function getDayPeriodRules(localeData) {
  const dayPeriodRules = localeData.get(`supplemental/dayPeriodRuleSet/${localeData.attributes.language}`);
  const rules = {};
  if (dayPeriodRules) {
    Object.keys(dayPeriodRules).forEach(key => {
      if (dayPeriodRules[key]._at) {
        rules[key] = dayPeriodRules[key]._at;
      } else {
        rules[key] = [dayPeriodRules[key]._from, dayPeriodRules[key]._before];
      }
    });
  }

  return rules;
}

// --- [50/100] getWeekendRange (angular/angular) ---

/**
 * Returns week-end range for a locale, based on US week days
 * @returns [number, number]
 * @original_repo angular/angular
 * @original_name getWeekendRange
 */
function getWeekendRange(localeData) {
  const startDay =
    localeData.get(`supplemental/weekData/weekendStart/${localeData.attributes.territory}`) ||
    localeData.get('supplemental/weekData/weekendStart/001');
  const endDay =
    localeData.get(`supplemental/weekData/weekendEnd/${localeData.attributes.territory}`) ||
    localeData.get('supplemental/weekData/weekendEnd/001');
  return [WEEK_DAYS.indexOf(startDay), WEEK_DAYS.indexOf(endDay)];
}

// --- [51/100] getNumberSettings (angular/angular) ---

/**
 * Returns the number symbols and formats for a locale
 * @returns [ symbols, formats ]
 * symbols: [ decimal, group, list, percentSign, plusSign, minusSign, exponential, superscriptingExponent, perMille, infinity, nan, timeSeparator, currencyDecimal?, currencyGroup? ]
 * formats: [ currency, decimal, percent, scientific ]
 * @original_repo angular/angular
 * @original_name getNumberSettings
 */
function getNumberSettings(localeData) {
  const decimalFormat = localeData.main('numbers/decimalFormats-numberSystem-latn/standard');
  const percentFormat = localeData.main('numbers/percentFormats-numberSystem-latn/standard');
  const scientificFormat = localeData.main('numbers/scientificFormats-numberSystem-latn/standard');
  const currencyFormat = localeData.main('numbers/currencyFormats-numberSystem-latn/standard');
  const symbols = localeData.main('numbers/symbols-numberSystem-latn');
  const symbolValues = [
    symbols.decimal,
    symbols.group,
    symbols.list,
    symbols.percentSign,
    symbols.plusSign,
    symbols.minusSign,
    symbols.exponential,
    symbols.superscriptingExponent,
    symbols.perMille,
    symbols.infinity,
    symbols.nan,
    symbols.timeSeparator,
  ];

  if (symbols.currencyDecimal || symbols.currencyGroup) {
    symbolValues.push(symbols.currencyDecimal);
  }

  if (symbols.currencyGroup) {
    symbolValues.push(symbols.currencyGroup);
  }

  return [
    symbolValues,
    [decimalFormat, percentFormat, currencyFormat, scientificFormat]
  ];
}

// --- [52/100] getCurrencySettings (angular/angular) ---

/**
 * Returns the currency symbol and name for a locale
 * @returns [ symbol, name ]
 * @original_repo angular/angular
 * @original_name getCurrencySettings
 */
function getCurrencySettings(locale, localeData) {
  const currencyInfo = localeData.main(`numbers/currencies`);
  let currentCurrency = '';

  // find the currency currently used in this country
  const currencies =
    localeData.get(`supplemental/currencyData/region/${localeData.attributes.territory}`) ||
    localeData.get(`supplemental/currencyData/region/${localeData.attributes.language.toUpperCase()}`);

  if (currencies) {
    currencies.some(currency => {
      const keys = Object.keys(currency);
      return keys.some(key => {
        if (currency[key]._from && !currency[key]._to) {
          return currentCurrency = key;
        }
      });
    });

    if (!currentCurrency) {
      throw new Error(`Unable to find currency for locale "${locale}"`);
    }
  }

  let currencySettings = [undefined, undefined];

  if (currentCurrency) {
    currencySettings = [currencyInfo[currentCurrency].symbol, currencyInfo[currentCurrency].displayName];
  }

  return currencySettings;
}

// --- [53/100] getPluralFunction (angular/angular) ---

/**
 * Returns the plural function for a locale
 * todo(ocombe): replace "cldr" extractPluralRuleFunction with our own extraction using "CldrJS"
 * because the 2 libs can become out of sync if they use different versions of the cldr database
 * @original_repo angular/angular
 * @original_name getPluralFunction
 */
function getPluralFunction(locale) {
  let fn = cldr.extractPluralRuleFunction(locale).toString();

  if (fn === EMPTY_RULE) {
    fn = DEFAULT_RULE;
  }

  fn = fn
    .replace(
      toRegExp('function anonymous(n\n/*``*/) {\n'),
      'function plural(n: number): number {\n  ')
    .replace(toRegExp('var'), 'let')
    .replace(toRegExp('if(typeof n==="string")n=parseInt(n,10);'), '')
    .replace(toRegExp('\n}'), ';\n}');

  // The replacement values must match the `Plural` enum from common.
  // We do not use the enum directly to avoid depending on that package.
  return fn
    .replace(toRegExp('"zero"'), ' 0')
    .replace(toRegExp('"one"'), ' 1')
    .replace(toRegExp('"two"'), ' 2')
    .replace(toRegExp('"few"'), ' 3')
    .replace(toRegExp('"many"'), ' 4')
    .replace(toRegExp('"other"'), ' 5');
}

// --- [54/100] removeDuplicates (angular/angular) ---

/**
 * To create smaller locale files, we remove duplicated data.
 * To be make this work we need to store similar data in arrays, if some value in an array
 * is undefined, we can take the previous defined value instead, because it means that it has
 * been deduplicated.
 * e.g.: [x, y, undefined, z, undefined, undefined]
 * The first undefined is equivalent to y, the second and third are equivalent to z
 * Note that the first value in an array is always defined.
 * 
 * Also since we need to know which data is assumed similar, it is important that we store those
 * similar data in arrays to mark the delimitation between values that have different meanings
 * (e.g. months and days).
 * 
 * For further size improvements, "undefined" values will be replaced by a constant in the arrays
 * as the last step of the file generation (in generateLocale and generateLocaleExtra).
 * e.g.: [x, y, undefined, z, undefined, undefined] will be [x, y, u, z, u, u]
 * @original_repo angular/angular
 * @original_name removeDuplicates
 */
function removeDuplicates(data) {
  const dedup = [data[0]];
  for(let i = 1; i < data.length; i++) {
    if (stringify(data[i]) !== stringify(data[i - 1])) {
      dedup.push(data[i]);
    } else {
      dedup.push(undefined);
    }
  }
  return dedup;
}

// --- [55/100] balance (angular/angular) ---

/**
 * Try to balance the brackets by adding closers on to the end of a string
 * for every bracket that is left open.
 * The chars at each index in the openers and closers should match (i.e openers = ['{', '('], closers = ['}', ')'])
 * 
 * @param {string} str The string to balance
 * @param {string[]} openers an array of chars that open a bracket
 * @param {string[]} closers an array of chars that close a brack
 * @returns the balanced string
 * @original_repo angular/angular
 * @original_name balance
 */
function balance(str, openers, closers) {
  const stack = [];

  // Add each open bracket to the stack, removing them when there is a matching closer
  str.split('').forEach(function(char) {
    const closerIndex = closers.indexOf(char);
    if (closerIndex !== -1 && stack[stack.length-1] === closerIndex) {
      stack.pop();
    } else {
      const openerIndex = openers.indexOf(char);
      if (openerIndex !== -1) {
        stack.push(openerIndex);
      }
    }
  });

  // Now the stack should contain all the unclosed brackets
  while(stack.length) {
    str += closers[stack.pop()];
  }

  return str;
}

// --- [56/100] getComponentConstructor (angular/angular) ---

/**
 * When this file is processed, the line below is replaced with the contents of the compiled TypeScript classes. {{SHARED_CODE}}
 * @original_repo angular/angular
 * @original_name getComponentConstructor
 */
function getComponentConstructor(name) {
    var serviceName = name + 'Directive';
    if ($injector.has(serviceName)) {
      var definitions = $injector.get(serviceName);
      if (definitions.length > 1) {
        throw new Error('too many directives named "' + name + '"');
      }
      return definitions[0].controller;
    } else {
      throw new Error('directive "' + name + '" is not registered');
    }
  }

// --- [57/100] file2moduleName (angular/angular) ---

/**
 * @license
 * Copyright Google Inc. All Rights Reserved.
 * 
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 * @original_repo angular/angular
 * @original_name file2moduleName
 */
function file2moduleName(filePath) {
  return filePath
      .replace(/\\/g, '/')
      // module name should be relative to `modules` and `tools` folder
      .replace(/.*\/modules\//, '')
      //  and 'dist' folder
      .replace(/.*\/dist\/js\/dev\/es5\//, '')
      // module name should not include `lib`, `web` folders
      // as they are wrapper packages for dart
      .replace(/\/web\//, '/')
      .replace(/\/lib\//, '/')
      // module name should not have a suffix
      .replace(/\.\w*$/, '');
}

// --- [58/100] _main (angular/angular) ---

/**
 * Functions - Definitions
 * @original_repo angular/angular
 * @original_name _main
 */
function _main() {
  // Detect path to `tsconfig.app.json`.
  const ngConfig = parse(readFileSync(NG_JSON, 'utf8'));
  const tsConfigPath = join(ROOT_DIR, ngConfig.projects.site.architect.build.options.tsConfig);

  // Enable Ivy in TS config.
  console.log(`\nModifying \`${tsConfigPath}\`...`);
  const oldTsConfigStr = readFileSync(tsConfigPath, 'utf8');
  const oldTsConfigObj = parse(oldTsConfigStr);
  const newTsConfigObj = extend(true, oldTsConfigObj, NG_COMPILER_OPTS);
  const newTsConfigStr = `${JSON.stringify(newTsConfigObj, null, 2)}\n`;
  console.log(`\nNew config: ${newTsConfigStr}`);
  writeFileSync(tsConfigPath, newTsConfigStr);

  // Run ngcc.
  const ngccArgs = '--loglevel debug --properties es2015 module';
  console.log(`\nRunning ngcc (with args: ${ngccArgs})...`);
  exec(`yarn ivy-ngcc ${ngccArgs}`);

  // Done.
  console.log('\nReady to build with Ivy!');
  console.log('(To switch back to ViewEngine (with packages from npm), undo the changes in ' +
              `\`${tsConfigPath}\` and run \`yarn aio-use-npm && yarn example-use-npm\`.)`);
}

// --- [59/100] loadTask (angular/angular) ---

/**
 * See `tools/gulp-tasks/README.md` for information about task loading.
 * @original_repo angular/angular
 * @original_name loadTask
 */
function loadTask(fileName, taskName) {
  const taskModule = require('./tools/gulp-tasks/' + fileName);
  const task = taskName ? taskModule[taskName] : taskModule;
  return task(gulp);
}

// --- [60/100] checkNodeModules (angular/angular) ---

/**
 * tslint:disable:no-console
 * @original_repo angular/angular
 * @original_name checkNodeModules
 */
function checkNodeModules(logOutput, purgeIfStale) {
  var yarnCheck = childProcess.spawnSync(
      'yarn check --integrity', {shell: true, cwd: path.resolve(__dirname, '../..')});

  var nodeModulesOK = yarnCheck.status === 0;
  if (nodeModulesOK) {
    if (logOutput) console.log(':-) npm dependencies are looking good!');
  } else {
    if (logOutput) console.error(':-( npm dependencies are stale or in an in unknown state!');
    if (purgeIfStale) {
      if (logOutput) console.log('    purging...');
      _deleteDir(path.join(PROJECT_ROOT, 'node_modules'));
    }
  }

  return nodeModulesOK;
}

// --- [61/100] _deleteDir (angular/angular) ---

/**
 * Custom implementation of recursive `rm` because we can't rely on the state of node_modules to
 * pull in existing module.
 * @original_repo angular/angular
 * @original_name _deleteDir
 */
function _deleteDir(path) {
  if (fs.existsSync(path)) {
    var subpaths = fs.readdirSync(path);
    subpaths.forEach(function(subpath) {
      var curPath = path + '/' + subpath;
      if (fs.lstatSync(curPath).isDirectory()) {
        _deleteDir(curPath);
      } else {
        fs.unlinkSync(curPath);
      }
    });
    fs.rmdirSync(path);
  }
}

// --- [62/100] createPackage (angular/angular) ---

/**
 * /* eslint no-console: "off"
 * @original_repo angular/angular
 * @original_name createPackage
 */
function createPackage(tutorialName) {

  const tutorialFilePath = `${CONTENTS_PATH}/getting-started/${tutorialName}.md`;
  const tutorialFile = readFileSync(tutorialFilePath, 'utf8');
  const examples = [];
  tutorialFile.replace(/<code-(?:pane|example) [^>]*path="([^"]+)"/g, (_, path) => examples.push('examples/' + path));

  if (examples.length) {
    console.log('The following example files are referenced in this getting-started:');
    console.log(examples.map(example => ' - ' + example).join('\n'));
  }

  return new Package('author-getting-started', [contentPackage])
    .config(function(readFilesProcessor) {
      readFilesProcessor.sourceFiles = [
        {
          basePath: CONTENTS_PATH,
          include: tutorialFilePath,
          fileReader: 'contentFileReader'
        },
        {
          basePath: CONTENTS_PATH,
          include: examples.map(example => resolve(CONTENTS_PATH, example)),
          fileReader: 'exampleFileReader'
        }
      ];
    });
}

// --- [63/100] _main (angular/angular) ---

/**
 * Helpers
 * @original_repo angular/angular
 * @original_name _main
 */
async function _main([buildNumber, compareUrl = '', circleToken = '']) {
  try {
    if (!buildNumber || isNaN(buildNumber)) {
      throw new Error(
          'Missing or invalid arguments.\n' +
          'Expected: buildNumber (number), compareUrl? (string), circleToken? (string)');
    }

    if (!compareUrl) {
      compareUrl = await getCompareUrl(buildNumber, circleToken);
    }

    const commitRangeMatch = COMPARE_URL_RE.exec(compareUrl)
    const commitRange = commitRangeMatch ? commitRangeMatch[1] : '';

    console.log(commitRange);
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
}

// --- [64/100] generateAllLocalesFile (angular/angular) ---

/**
 * Generate a file that contains all locale to import for closure.
 * Tree shaking will only keep the data for the `goog.LOCALE` locale.
 * @original_repo angular/angular
 * @original_name generateAllLocalesFile
 */
function generateAllLocalesFile(LOCALES, ALIASES) {
  const existingLocalesAliases = {};
  const existingLocalesData = {};

  // for each locale, get the data and the list of equivalent locales
  LOCALES.forEach(locale => {
    const eqLocales = new Set();
    eqLocales.add(locale);
    if (locale.match(/-/)) {
      eqLocales.add(locale.replace(/-/g, '_'));
    }

    // check for aliases
    const alias = ALIASES[locale];
    if (alias) {
      eqLocales.add(alias);

      if (alias.match(/-/)) {
        eqLocales.add(alias.replace(/-/g, '_'));
      }

      // to avoid duplicated "case" we regroup all locales in the same "case"
      // the simplest way to do that is to have alias aliases
      // e.g. 'no' --> 'nb', 'nb' --> 'no-NO'
      // which means that we'll have 'no', 'nb' and 'no-NO' in the same "case"
      const aliasKeys = Object.keys(ALIASES);
      for (let i = 0; i < aliasKeys.length; i++) {
        const aliasValue = ALIASES[alias];
        if (aliasKeys.indexOf(alias) !== -1 && !eqLocales.has(aliasValue)) {
          eqLocales.add(aliasValue);

          if (aliasValue.match(/-/)) {
            eqLocales.add(aliasValue.replace(/-/g, '_'));
          }
        }
      }
    }

    for (let l of eqLocales) {
      // find the existing content file
      const path = `${RELATIVE_I18N_DATA_FOLDER}/${l}.ts`;
      if (fs.existsSync(`${RELATIVE_I18N_DATA_FOLDER}/${l}.ts`)) {
        const localeName = formatLocale(locale);
        existingLocalesData[locale] =
            fs.readFileSync(path, 'utf8')
                .replace(`${HEADER}\n`, '')
                .replace('export default ', `export const locale_${localeName} = `)
                .replace('function plural', `function plural_${localeName}`)
                .replace(/,(\n  | )plural/, `, plural_${localeName}`)
                .replace('const u = undefined;\n\n', '');
      }
    }

    existingLocalesAliases[locale] = eqLocales;
  });

  function generateCases(locale) {
    let str = '';
    let locales = [];
    const eqLocales = existingLocalesAliases[locale];
    for (let l of eqLocales) {
      str += `case '${l}':\n`;
      locales.push(`'${l}'`);
    }
    let localesStr = '[' + locales.join(',') + ']';

    str += `  l = locale_${formatLocale(locale)};
    locales = ${localesStr};
    break;\n`;
    return str;
  }

  function formatLocale(locale) { return locale.replace(/-/g, '_'); }
  // clang-format off
  return `${HEADER}
import {registerLocaleData} from '../src/i18n/locale_data';

const u = undefined;

${LOCALES.map(locale => `${existingLocalesData[locale]}`).join('\n')}

let l: any;
let locales: string[] = [];

switch (goog.LOCALE) {
${LOCALES.map(locale => generateCases(locale)).join('')}}

if(l) {
  locales.forEach(locale => registerLocaleData(l, locale));
}
`;
  // clang-format on
}

// --- [65/100] tsc (angular/angular) ---

/**
 * @license
 * Copyright Google Inc. All Rights Reserved.
 * 
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 * @original_repo angular/angular
 * @original_name tsc
 */
function tsc(projectPath, done) {
  const path = require('path');
  const platformScriptPath = require('./platform-script-path');
  const childProcess = require('child_process');

  childProcess
      .spawn(
          path.join(__dirname, platformScriptPath('../../node_modules/.bin/tsc')),
          ['-p', path.join(__dirname, '../..', projectPath)], {stdio: 'inherit'})
      .on('close', done);
}

// --- [66/100] inlineTagDefs (angular/angular) ---

/**
 * Teach remark about inline tags, so that it neither wraps block level
 * tags in paragraphs nor processes the text within the tag.
 * @original_repo angular/angular
 * @original_name inlineTagDefs
 */
function inlineTagDefs() {
    const Parser = this.Parser;
    const inlineTokenizers = Parser.prototype.inlineTokenizers;
    const inlineMethods = Parser.prototype.inlineMethods;
    const blockTokenizers = Parser.prototype.blockTokenizers;
    const blockMethods = Parser.prototype.blockMethods;

    blockTokenizers.inlineTag = tokenizeInlineTag;
    blockMethods.splice(blockMethods.indexOf('paragraph'), 0, 'inlineTag');

    inlineTokenizers.inlineTag = tokenizeInlineTag;
    inlineMethods.splice(blockMethods.indexOf('text'), 0, 'inlineTag');
    tokenizeInlineTag.notInLink = true;
    tokenizeInlineTag.locator = inlineTagLocator;

    function tokenizeInlineTag(eat, value, silent) {
      const match = /^\{@[^\s\}]+[^\}]*\}/.exec(value);

      if (match) {
        if (silent) {
          return true;
        }
        return eat(match[0])({
          'type': 'inlineTag',
          'value': match[0]
        });
      }
    }

    function inlineTagLocator(value, fromIndex) {
      return value.indexOf('{@', fromIndex);
    }
  }

// --- [67/100] plainHTMLBlocks (angular/angular) ---

/**
 * Teach remark that some HTML blocks never include markdown
 * @original_repo angular/angular
 * @original_name plainHTMLBlocks
 */
function plainHTMLBlocks() {

    const plainBlocks = ['code-example', 'code-tabs'];

    // Create matchers for each block
    const anyBlockMatcher = new RegExp('^' + createOpenMatcher(`(${plainBlocks.join('|')})`));

    const Parser = this.Parser;
    const blockTokenizers = Parser.prototype.blockTokenizers;
    const blockMethods = Parser.prototype.blockMethods;

    blockTokenizers.plainHTMLBlocks = tokenizePlainHTMLBlocks;
    blockMethods.splice(blockMethods.indexOf('html'), 0, 'plainHTMLBlocks');

    function tokenizePlainHTMLBlocks(eat, value, silent) {
      const openMatch = anyBlockMatcher.exec(value);
      if (openMatch) {
        const blockName = openMatch[1];
        try {
          const fullMatch = matchRecursiveRegExp(value, createOpenMatcher(blockName), createCloseMatcher(blockName))[0];
          if (silent || !fullMatch) {
            // either we are not eating (silent) or the match failed
            return !!fullMatch;
          }
          return eat(fullMatch[0])({
            type: 'html',
            value: fullMatch[0]
          });
        } catch(e) {
          this.file.fail('Unmatched plain HTML block tag ' + e.message);
        }
      }
    }
  }

// --- [68/100] setConf (angular/angular) ---

/**
 * Helper function to warn when a user specified value is being overwritten
 * @original_repo angular/angular
 * @original_name setConf
 */
function setConf(conf, name, value, msg) {
  if (conf[name] && conf[name] !== value) {
    console.warn(
        `Your protractor configuration specifies an option which is overwritten by Bazel: '${name}' ${msg}`);
  }
  conf[name] = value;
}

// --- [69/100] isArray (angular/angular) ---

/**
 * polyfills
 * @original_repo angular/angular
 * @original_name isArray
 */
function isArray(obj) {
    if (Array.isArray) {
      return Array.isArray(obj);
    } else {
      return Object.prototype.toString.call(obj) === '[object Array]';
    }
  }

// --- [70/100] internalStringify (angular/angular) ---

/**
 * End
 * @original_repo angular/angular
 * @original_name internalStringify
 */
function internalStringify(holder, key) {
    var buffer, res;

    // Replace the value, if necessary
    var obj_part = getReplacedValueOrUndefined(holder, key);

    if (obj_part && !isDate(obj_part)) {
      // unbox objects
      // don't unbox dates, since will turn it into number
      obj_part = obj_part.valueOf();
    }
    switch (typeof obj_part) {
      case 'boolean':
        return obj_part.toString();

      case 'number':
        if (isNaN(obj_part) || !isFinite(obj_part)) {
          return 'null';
        }
        return obj_part.toString();

      case 'string':
        return escapeString(obj_part.toString());

      case 'object':
        if (obj_part === null) {
          return 'null';
        } else if (isArray(obj_part)) {
          checkForCircular(obj_part);
          buffer = '[';
          objStack.push(obj_part);

          for (var i = 0; i < obj_part.length; i++) {
            res = internalStringify(obj_part, i);
            if (res === null) {
              buffer += 'null';
            } /* else if (typeof res === 'undefined') {  // modified to support empty array values
              buffer += '';
            }*/ else {
              buffer += res;
            }
            if (i < obj_part.length - 1) {
              buffer += ',';
            }
          }
          objStack.pop();
          buffer += ']';
        } else {
          checkForCircular(obj_part);
          buffer = '{';
          var nonEmpty = false;
          objStack.push(obj_part);
          for (var prop in obj_part) {
            if (obj_part.hasOwnProperty(prop)) {
              var value = internalStringify(obj_part, prop);
              if (typeof value !== 'undefined' && value !== null) {
                nonEmpty = true;
                key = isWord(prop) && !quoteKeys ? prop : escapeString(prop, quoteKeys);
                buffer += key + ':' + value + ',';
              }
            }
          }
          objStack.pop();
          if (nonEmpty) {
            buffer = buffer.substring(0, buffer.length - 1) + '}';
          } else {
            buffer = '{}';
          }
        }
        return buffer;
      default:
        // functions and undefined should be ignored
        return undefined;
    }
  }

// --- [71/100] runProtractorAoT (angular/angular) ---

/**
 * Run e2e tests over the AOT build for projects that examples it.
 * @original_repo angular/angular
 * @original_name runProtractorAoT
 */
function runProtractorAoT(appDir, outputFile) {
  fs.appendFileSync(outputFile, '++ AoT version ++\n');
  const aotBuildSpawnInfo = spawnExt('yarn', ['build:aot'], {cwd: appDir});
  let promise = aotBuildSpawnInfo.promise;

  const copyFileCmd = 'copy-dist-files.js';
  if (fs.existsSync(appDir + '/' + copyFileCmd)) {
    promise = promise.then(() => spawnExt('node', [copyFileCmd], {cwd: appDir}).promise);
  }
  const aotRunSpawnInfo = spawnExt('yarn', ['serve:aot'], {cwd: appDir}, true);
  return runProtractorSystemJS(promise, appDir, aotRunSpawnInfo, outputFile);
}

// --- [72/100] reportStatus (angular/angular) ---

/**
 * Report final status.
 * @original_repo angular/angular
 * @original_name reportStatus
 */
function reportStatus(status, outputFile) {
  let log = [''];

  log.push('Suites ignored due to legacy guides:');
  IGNORED_EXAMPLES.filter(example => !fixmeIvyExamples.find(ex => ex.startsWith(example)))
      .forEach(function(val) { log.push('  ' + val); });

  if (argv.ivy) {
    log.push('');
    log.push('Suites ignored due to breakage with Ivy:');
    fixmeIvyExamples.forEach(function(val) { log.push('  ' + val); });
  }

  log.push('');
  log.push('Suites passed:');
  status.passed.forEach(function(val) { log.push('  ' + val); });

  if (status.failed.length == 0) {
    log.push('All tests passed');
  } else {
    log.push('Suites failed:');
    status.failed.forEach(function(val) { log.push('  ' + val); });
  }
  log.push('\nElapsed time: ' + status.elapsedTime + ' seconds');
  log = log.join('\n');
  console.log(log);
  fs.appendFileSync(outputFile, log);
}

// --- [73/100] spawnExt (angular/angular) ---

/**
 * Returns both a promise and the spawned process so that it can be killed if needed.
 * @original_repo angular/angular
 * @original_name spawnExt
 */
function spawnExt(command, args, options, ignoreClose = false,
                  printMessage = msg => process.stdout.write(msg)) {
  let proc;
  const promise = new Promise((resolve, reject) => {
    let descr = command + ' ' + args.join(' ');
    let processOutput = '';
    printMessage(`running: ${descr}\n`);
    try {
      proc = xSpawn.spawn(command, args, options);
    } catch (e) {
      console.log(e);
      reject(e);
      return {proc: null, promise};
    }
    proc.stdout.on('data', printMessage);
    proc.stderr.on('data', printMessage);

    proc.on('close', function(returnCode) {
      printMessage(`completed: ${descr}\n\n`);
      // Many tasks (e.g., tsc) complete but are actually errors;
      // Confirm return code is zero.
      returnCode === 0 || ignoreClose ? resolve(0) : reject(returnCode);
    });
    proc.on('error', function(data) {
      printMessage(`completed with error: ${descr}\n\n`);
      printMessage(`${data.toString()}\n`);
      reject(data);
    });
  });
  return {proc, promise};
}

// --- [74/100] loadExampleConfig (angular/angular) ---

/**
 * Load configuration for an example. Used for SystemJS
 * @original_repo angular/angular
 * @original_name loadExampleConfig
 */
function loadExampleConfig(exampleFolder) {
  // Default config.
  let config = {build: 'build', run: 'serve:e2e'};

  try {
    const exampleConfig = fs.readJsonSync(`${exampleFolder}/${EXAMPLE_CONFIG_FILENAME}`);
    Object.assign(config, exampleConfig);
  } catch (e) {
  }

  return config;
}

// --- [75/100] logSpecs (angular/angular) ---

/**
 * Log the specs (for debugging purposes). `e2eSpecPaths` is of type: `{[type: string]: string[]}` (where `type` is `systemjs`, `cli, etc.)
 * @original_repo angular/angular
 * @original_name logSpecs
 */
function logSpecs(e2eSpecPaths) {
  Object.keys(e2eSpecPaths).forEach(type => {
    const paths = e2eSpecPaths[type];

    console.log(`  ${type.toUpperCase()}:`);
    console.log(paths.map(p => `    ${p}`).join('\n'));
  });
}

// --- [76/100] getNextLNodeWithProjection (angular/angular) ---

/**
 * @license
 * Copyright Google Inc. All Rights Reserved.
 * 
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 * 
 * @license
 * Copyright Google Inc. All Rights Reserved.
 * 
 * Use of this source code is governed by an MIT-style license that can be
 * found in the LICENSE file at https://angular.io/license
 * @original_repo angular/angular
 * @original_name getNextLNodeWithProjection
 */
function
  getNextLNodeWithProjection(node) {
    var pNextOrParent = node.pNextOrParent;
    return pNextOrParent ? 1 == (3 & pNextOrParent.flags) ? null : pNextOrParent : node.next;
  }

// --- [77/100] _main (angular/angular) ---

/**
 * Helpers
 * @original_repo angular/angular
 * @original_name _main
 */
async function _main(repository, prNumber) {
  console.log(`Determining target branch for PR ${prNumber} on ${repository}.`);
  const targetBranch = await determineTargetBranch(repository, prNumber);
  console.log(`Target branch is ${targetBranch}.`);
  await exec(`git fetch origin ${targetBranch}`);
  console.log(`Rebasing current branch on ${targetBranch}.`);
  await exec(`git rebase origin/${targetBranch}`);
  console.log('Rebase successful.');
}

// --- [78/100] Reporter (angular/angular) ---

/**
 * See http://jasmine.github.io/2.1/custom_reporter.html
 * @original_repo angular/angular
 * @original_name Reporter
 */
function Reporter(options) {
  var _defaultOutputFile = path.resolve(__dirname, '../../protractor-results.txt');
  options.outputFile = options.outputFile || _defaultOutputFile;

  var _root = { appDir: options.appDir, suites: [] };
  log('AppDir: ' + options.appDir, +1);
  var _currentSuite;

  this.suiteStarted = function(suite) {
    _currentSuite = { description: suite.description, status: null, specs: [] };
    _root.suites.push(_currentSuite);
    log('Suite: ' + suite.description, +1);
  };

  this.suiteDone = function(suite) {
    var statuses = _currentSuite.specs.map(function(spec) {
      return spec.status;
    });
    statuses = _.uniq(statuses);
    var status = statuses.indexOf('failed') >= 0 ? 'failed' : statuses.join(', ');
    _currentSuite.status = status;
    log('Suite ' + _currentSuite.status + ': ' + suite.description, -1);
  };

  this.specStarted = function(spec) {

  };

  this.specDone = function(spec) {
    var currentSpec = {
      description: spec.description,
      status: spec.status
    };
    if (spec.failedExpectations.length > 0) {
      currentSpec.failedExpectations = spec.failedExpectations;
    }

    _currentSuite.specs.push(currentSpec);
    log(spec.status + ' - ' + spec.description);
    if (spec.status === 'failed') {
      spec.failedExpectations.forEach(function(err) {
        log(err.message);
      });
    }
  };

  this.jasmineDone = function() {
    outputFile = options.outputFile;
    //// Alternate approach - just stringify the _root - not as pretty
    //// but might be more useful for automation.
    // var output = JSON.stringify(_root, null, 2);
    var output = formatOutput(_root);
    fs.appendFileSync(outputFile, output);
  };

  // for output file output
  function formatOutput(output) {
    var indent = '  ';
    var pad = '  ';
    var results = [];
    results.push('AppDir:' + output.appDir);
    output.suites.forEach(function(suite) {
      results.push(pad + 'Suite: ' + suite.description + ' -- ' + suite.status);
      pad+=indent;
      suite.specs.forEach(function(spec) {
        results.push(pad + spec.status + ' - ' + spec.description);
        if (spec.failedExpectations) {
          pad+=indent;
          spec.failedExpectations.forEach(function (fe) {
            results.push(pad + 'message: ' + fe.message);
          });
          pad=pad.substr(2);
        }
      });
      pad = pad.substr(2);
      results.push('');
    });
    results.push('');
    return results.join('\n');
  }

  // for console output
  var _pad;
  function log(str, indent) {
    _pad = _pad || '';
    if (indent == -1) {
      _pad = _pad.substr(2);
    }
    console.log(_pad + str);
    if (indent == 1) {
      _pad = _pad + '  ';
    }
  }

}

// --- [79/100] formatOutput (angular/angular) ---

/**
 * for output file output
 * @original_repo angular/angular
 * @original_name formatOutput
 */
function formatOutput(output) {
    var indent = '  ';
    var pad = '  ';
    var results = [];
    results.push('AppDir:' + output.appDir);
    output.suites.forEach(function(suite) {
      results.push(pad + 'Suite: ' + suite.description + ' -- ' + suite.status);
      pad+=indent;
      suite.specs.forEach(function(spec) {
        results.push(pad + spec.status + ' - ' + spec.description);
        if (spec.failedExpectations) {
          pad+=indent;
          spec.failedExpectations.forEach(function (fe) {
            results.push(pad + 'message: ' + fe.message);
          });
          pad=pad.substr(2);
        }
      });
      pad = pad.substr(2);
      results.push('');
    });
    results.push('');
    return results.join('\n');
  }

// --- [80/100] gulpStatus (angular/angular) ---

/**
 * Gulp stream that wraps the gulp-git status,
 * only returns untracked files, and converts
 * the stdout into a stream of files.
 * @original_repo angular/angular
 * @original_name gulpStatus
 */
function gulpStatus() {
  const Vinyl = require('vinyl');
  const path = require('path');
  const gulpGit = require('gulp-git');
  const through = require('through2');
  const srcStream = through.obj();

  const opt = {cwd: process.cwd()};

  // https://git-scm.com/docs/git-status#_short_format
  const RE_STATUS = /((\s\w)|(\w+)|\?{0,2})\s([\w\+\-\/\\\.]+)(\s->\s)?([\w\+\-\/\\\.]+)*\n{0,1}/gm;

  gulpGit.status({args: '--porcelain', quiet: true}, function(err, stdout) {
    if (err) return srcStream.emit('error', err);

    const data = stdout.toString();
    let currentMatch;

    while ((currentMatch = RE_STATUS.exec(data)) !== null) {
      // status
      const status = currentMatch[1].trim().toLowerCase();

      // We only care about untracked files and renamed files
      if (!new RegExp(/r|\?/i).test(status)) {
        continue;
      }

      // file path
      const currentFilePath = currentMatch[4];

      // new file path in case its been moved
      const newFilePath = currentMatch[6];
      const filePath = newFilePath || currentFilePath;

      srcStream.write(new Vinyl({
        path: path.resolve(opt.cwd, filePath),
        cwd: opt.cwd,
      }));

      RE_STATUS.lastIndex++;
    }

    srcStream.end();
  });

  return srcStream;
}

// --- [81/100] _main (angular/angular) ---

/**
 * Functions - Definitions
 * @original_repo angular/angular
 * @original_name _main
 */
function _main() {
  const srcIndexPath = join(DIST_DIR, 'index.html');
  const src404BodyPath = join(SRC_DIR, '404-body.html');
  const dst404PagePath = join(DIST_DIR, '404.html');

  const srcIndexContent = readFileSync(srcIndexPath, 'utf8');
  const src404BodyContent = readFileSync(src404BodyPath, 'utf8');
  const dst404PageContent = srcIndexContent.replace(/<body>[\s\S]+<\/body>/, src404BodyContent);

  if (dst404PageContent === srcIndexContent) {
    throw new Error(
        'Failed to generate \'404.html\'. ' +
        'The content of \'index.html\' does not match the expected pattern.');
  }

  writeFileSync(dst404PagePath, dst404PageContent);
}

// --- [82/100] getAdditionalModulePaths (facebook/create-react-app) ---

/**
 * Get the baseUrl of a compilerOptions object.
 * 
 * @param {Object} options
 * @original_repo facebook/create-react-app
 * @original_name getAdditionalModulePaths
 */
function getAdditionalModulePaths(options = {}) {
  const baseUrl = options.baseUrl;

  // We need to explicitly check for null and undefined (and not a falsy value) because
  // TypeScript treats an empty string as `.`.
  if (baseUrl == null) {
    // If there's no baseUrl set we respect NODE_PATH
    // Note that NODE_PATH is deprecated and will be removed
    // in the next major release of create-react-app.

    const nodePath = process.env.NODE_PATH || '';
    return nodePath.split(path.delimiter).filter(Boolean);
  }

  const baseUrlResolved = path.resolve(paths.appPath, baseUrl);

  // We don't need to do anything if `baseUrl` is set to `node_modules`. This is
  // the default behavior.
  if (path.relative(paths.appNodeModules, baseUrlResolved) === '') {
    return null;
  }

  // Allow the user set the `baseUrl` to `appSrc`.
  if (path.relative(paths.appSrc, baseUrlResolved) === '') {
    return [paths.appSrc];
  }

  // Otherwise, throw an error.
  throw new Error(
    chalk.red.bold(
      "Your project's `baseUrl` can only be set to `src` or `node_modules`." +
        ' Create React App does not support other values at this time.'
    )
  );
}

// --- [83/100] isSafeToCreateProjectIn (facebook/create-react-app) ---

/**
 * If project only contains files generated by GH, it’s safe. Also, if project contains remnant error logs from a previous installation, lets remove them now. We also special case IJ-based products .idea because it integrates with CRA: https://github.com/facebook/create-react-app/pull/368#issuecomment-243446094
 * @original_repo facebook/create-react-app
 * @original_name isSafeToCreateProjectIn
 */
function isSafeToCreateProjectIn(root, name) {
  const validFiles = [
    '.DS_Store',
    'Thumbs.db',
    '.git',
    '.gitignore',
    '.idea',
    'README.md',
    'LICENSE',
    '.hg',
    '.hgignore',
    '.hgcheck',
    '.npmignore',
    'mkdocs.yml',
    'docs',
    '.travis.yml',
    '.gitlab-ci.yml',
    '.gitattributes',
  ];
  console.log();

  const conflicts = fs
    .readdirSync(root)
    .filter(file => !validFiles.includes(file))
    // IntelliJ IDEA creates module files before CRA is launched
    .filter(file => !/\.iml$/.test(file))
    // Don't treat log files from previous installation as conflicts
    .filter(
      file => !errorLogFilePatterns.some(pattern => file.indexOf(pattern) === 0)
    );

  if (conflicts.length > 0) {
    console.log(
      `The directory ${chalk.green(name)} contains files that could conflict:`
    );
    console.log();
    for (const file of conflicts) {
      console.log(`  ${file}`);
    }
    console.log();
    console.log(
      'Either try using a new directory name, or remove the files listed above.'
    );

    return false;
  }

  // Remove any remnant files from a previous installation
  const currentFiles = fs.readdirSync(path.join(root));
  currentFiles.forEach(file => {
    errorLogFilePatterns.forEach(errorLogFilePattern => {
      // This will catch `(npm-debug|yarn-error|yarn-debug).log*` files
      if (file.indexOf(errorLogFilePattern) === 0) {
        fs.removeSync(path.join(root, file));
      }
    });
  });
  return true;
}

// --- [84/100] handleSuccess (facebook/create-react-app) ---

/**
 * Successful compilation.
 * @original_repo facebook/create-react-app
 * @original_name handleSuccess
 */
function handleSuccess() {
  clearOutdatedErrors();

  var isHotUpdate = !isFirstCompilation;
  isFirstCompilation = false;
  hasCompileErrors = false;

  // Attempt to apply hot updates or reload.
  if (isHotUpdate) {
    tryApplyUpdates(function onHotUpdateSuccess() {
      // Only dismiss it when we're sure it's a hot update.
      // Otherwise it would flicker right before the reload.
      tryDismissErrorOverlay();
    });
  }
}

// --- [85/100] printFileSizesAfterBuild (facebook/create-react-app) ---

/**
 * Prints a detailed summary of build files.
 * @original_repo facebook/create-react-app
 * @original_name printFileSizesAfterBuild
 */
function printFileSizesAfterBuild(
  webpackStats,
  previousSizeMap,
  buildFolder,
  maxBundleGzipSize,
  maxChunkGzipSize
) {
  var root = previousSizeMap.root;
  var sizes = previousSizeMap.sizes;
  var assets = (webpackStats.stats || [webpackStats])
    .map(stats =>
      stats
        .toJson({ all: false, assets: true })
        .assets.filter(asset => canReadAsset(asset.name))
        .map(asset => {
          var fileContents = fs.readFileSync(path.join(root, asset.name));
          var size = gzipSize(fileContents);
          var previousSize = sizes[removeFileNameHash(root, asset.name)];
          var difference = getDifferenceLabel(size, previousSize);
          return {
            folder: path.join(
              path.basename(buildFolder),
              path.dirname(asset.name)
            ),
            name: path.basename(asset.name),
            size: size,
            sizeLabel:
              filesize(size) + (difference ? ' (' + difference + ')' : ''),
          };
        })
    )
    .reduce((single, all) => all.concat(single), []);
  assets.sort((a, b) => b.size - a.size);
  var longestSizeLabelLength = Math.max.apply(
    null,
    assets.map(a => stripAnsi(a.sizeLabel).length)
  );
  var suggestBundleSplitting = false;
  assets.forEach(asset => {
    var sizeLabel = asset.sizeLabel;
    var sizeLength = stripAnsi(sizeLabel).length;
    if (sizeLength < longestSizeLabelLength) {
      var rightPadding = ' '.repeat(longestSizeLabelLength - sizeLength);
      sizeLabel += rightPadding;
    }
    var isMainBundle = asset.name.indexOf('main.') === 0;
    var maxRecommendedSize = isMainBundle
      ? maxBundleGzipSize
      : maxChunkGzipSize;
    var isLarge = maxRecommendedSize && asset.size > maxRecommendedSize;
    if (isLarge && path.extname(asset.name) === '.js') {
      suggestBundleSplitting = true;
    }
    console.log(
      '  ' +
        (isLarge ? chalk.yellow(sizeLabel) : sizeLabel) +
        '  ' +
        chalk.dim(asset.folder + path.sep) +
        chalk.cyan(asset.name)
    );
  });
  if (suggestBundleSplitting) {
    console.log();
    console.log(
      chalk.yellow('The bundle size is significantly larger than recommended.')
    );
    console.log(
      chalk.yellow(
        'Consider reducing it with code splitting: https://goo.gl/9VhYWB'
      )
    );
    console.log(
      chalk.yellow(
        'You can also analyze the project dependencies: https://goo.gl/LeUzfb'
      )
    );
  }
}

// --- [86/100] openBrowser (facebook/create-react-app) ---

/**
 * Reads the BROWSER environment variable and decides what to do with it. Returns
 * true if it opened a browser or ran a node.js script, otherwise false.
 * @original_repo facebook/create-react-app
 * @original_name openBrowser
 */
function openBrowser(url) {
  const { action, value } = getBrowserEnv();
  switch (action) {
    case Actions.NONE:
      // Special case: BROWSER="none" will prevent opening completely.
      return false;
    case Actions.SCRIPT:
      return executeNodeScript(value, url);
    case Actions.BROWSER:
      return startBrowserProcess(value, url);
    default:
      throw new Error('Not implemented.');
  }
}

// --- [87/100] onProxyError (facebook/create-react-app) ---

/**
 * We need to provide a custom onError function for httpProxyMiddleware. It allows us to log custom error messages on the console.
 * @original_repo facebook/create-react-app
 * @original_name onProxyError
 */
function onProxyError(proxy) {
  return (err, req, res) => {
    const host = req.headers && req.headers.host;
    console.log(
      chalk.red('Proxy error:') +
        ' Could not proxy request ' +
        chalk.cyan(req.url) +
        ' from ' +
        chalk.cyan(host) +
        ' to ' +
        chalk.cyan(proxy) +
        '.'
    );
    console.log(
      'See https://nodejs.org/api/errors.html#errors_common_system_errors for more information (' +
        chalk.cyan(err.code) +
        ').'
    );
    console.log();

    // And immediately send the proper error response to the client.
    // Otherwise, the request will eventually timeout with ERR_EMPTY_RESPONSE on the client side.
    if (res.writeHead && !res.headersSent) {
      res.writeHead(500);
    }
    res.end(
      'Proxy error: Could not proxy request ' +
        req.url +
        ' from ' +
        host +
        ' to ' +
        proxy +
        ' (' +
        err.code +
        ').'
    );
  };
}

// --- [88/100] unknown (facebook/create-react-app) ---

/**
 * For single page apps, we generally want to fallback to /index.html. However we also want to respect `proxy` for API calls. So if `proxy` is specified as a string, we need to decide which fallback to use. We use a heuristic: We want to proxy all the requests that are not meant for static assets and as all the requests for static assets will be using `GET` method, we can proxy all non-`GET` requests. For `GET` requests, if request `accept`s text/html, we pick /index.html. Modern browsers include text/html into `accept` header when navigating. However API calls like `fetch()` won’t generally accept text/html. If this heuristic doesn’t work well for you, use `src/setupProxy.js`.
 * @original_repo facebook/create-react-app
 * @original_name unknown
 */
function(pathname, req) {
        return (
          req.method !== 'GET' ||
          (mayProxy(pathname) &&
            req.headers.accept &&
            req.headers.accept.indexOf('text/html') === -1)
        );
      }

// --- [89/100] getServedPath (facebook/create-react-app) ---

/**
 * We use `PUBLIC_URL` environment variable or "homepage" field to infer "public path" at which the app is served. Webpack needs to know it to put the right <script> hrefs into HTML even in single-page apps that may serve index.html for nested URLs like /todos/42. We can't use a relative path in HTML because we don't want to load something like /todos/42/static/js/bundle.7289d.js. We have to know the root.
 * @original_repo facebook/create-react-app
 * @original_name getServedPath
 */
function getServedPath(appPackageJson) {
  const publicUrl = getPublicUrl(appPackageJson);
  const servedUrl =
    envPublicUrl || (publicUrl ? url.parse(publicUrl).pathname : '/');
  return ensureSlash(servedUrl, true);
}

// --- [90/100] ignoreMomentLocale (ant-design/ant-design) ---

/**
 * noParse still leave `require('./locale' + name)` in dist files ignore is better: http://stackoverflow.com/q/25384360
 * @original_repo ant-design/ant-design
 * @original_name ignoreMomentLocale
 */
function ignoreMomentLocale(webpackConfig) {
  delete webpackConfig.module.noParse;
  webpackConfig.plugins.push(new webpack.IgnorePlugin(/^\.\/locale$/, /moment$/));
}

// --- [91/100] finalizeCompile (ant-design/ant-design) ---

/**
 * We need compile additional content for antd user
 * @original_repo ant-design/ant-design
 * @original_name finalizeCompile
 */
function finalizeCompile() {
  if (fs.existsSync(path.join(__dirname, './lib'))) {
    // Build package.json version to lib/version/index.js
    // prevent json-loader needing in user-side
    const versionFilePath = path.join(process.cwd(), 'lib', 'version', 'index.js');
    const versionFileContent = fs.readFileSync(versionFilePath).toString();
    fs.writeFileSync(
      versionFilePath,
      versionFileContent.replace(
        /require\(('|")\.\.\/\.\.\/package\.json('|")\)/,
        `{ version: '${packageInfo.version}' }`,
      ),
    );
    // eslint-disable-next-line
    console.log('Wrote version into lib/version/index.js');

    // Build package.json version to lib/version/index.d.ts
    // prevent https://github.com/ant-design/ant-design/issues/4935
    const versionDefPath = path.join(process.cwd(), 'lib', 'version', 'index.d.ts');
    fs.writeFileSync(
      versionDefPath,
      `declare var _default: "${packageInfo.version}";\nexport default _default;\n`,
    );
    // eslint-disable-next-line
    console.log('Wrote version into lib/version/index.d.ts');

    // Build a entry less file to dist/antd.less
    const componentsPath = path.join(process.cwd(), 'components');
    let componentsLessContent = '';
    // Build components in one file: lib/style/components.less
    fs.readdir(componentsPath, (err, files) => {
      files.forEach(file => {
        if (fs.existsSync(path.join(componentsPath, file, 'style', 'index.less'))) {
          componentsLessContent += `@import "../${path.join(file, 'style', 'index.less')}";\n`;
        }
      });
      fs.writeFileSync(
        path.join(process.cwd(), 'lib', 'style', 'components.less'),
        componentsLessContent,
      );
    });
  }
}

// --- [92/100] doRollup (30-seconds/30-seconds-of-code) ---

/**
 * Builds the UMD + ESM files to the ./dist directory.
 * @original_repo 30-seconds/30-seconds-of-code
 * @original_name doRollup
 */
async function doRollup() {
  // Plugins
  const es5 = babel({ presets: ['@babel/preset-env'] });
  const min = minify({ comments: false });

  const output = format => file => ({
    format,
    file,
    name: MODULE_NAME
  });

  const umd = output('umd');
  const esm = output('es');

  const bundle = await rollup({ input: ROLLUP_INPUT_FILE });
  const bundleES5 = await rollup({ input: ROLLUP_INPUT_FILE, plugins: [es5] });
  const bundleES5Min = await rollup({
    input: ROLLUP_INPUT_FILE,
    plugins: [es5, min]
  });

  const baseName = `${DIST_PATH}/${MODULE_NAME}`;

  // UMD ES2018
  await bundle.write(umd(`${baseName}.js`));
  // ESM ES2018
  await bundle.write(esm(`${baseName}.esm.js`));
  // UMD ES5
  await bundleES5.write(umd(`${baseName}.es5.js`));
  // UMD ES5 min
  await bundleES5Min.write(umd(`${baseName}.es5.min.js`));
}

// --- [93/100] build (30-seconds/30-seconds-of-code) ---

/**
 * Starts the build process.
 * @original_repo 30-seconds/30-seconds-of-code
 * @original_name build
 */
async function build() {
  console.time('Packager');

  let requires = [];
  let esmExportString = '';
  let cjsExportString = '';

  try {
    if (!fs.existsSync(DIST_PATH)) fs.mkdirSync(DIST_PATH);
    fs.writeFileSync(ROLLUP_INPUT_FILE, '');
    fs.writeFileSync(TEST_MODULE_FILE, '');

    // All the snippets that are Node.js-based and will break in a browser
    // environment
    const nodeSnippets = fs
      .readFileSync('tag_database', 'utf8')
      .split('\n')
      .filter(v => v.search(/:.*node/g) !== -1)
      .map(v => v.slice(0, v.indexOf(':')));

    const snippets = fs.readdirSync(SNIPPETS_PATH);
    const archivedSnippets = fs
      .readdirSync(SNIPPETS_ARCHIVE_PATH)
      .filter(v => v !== 'README.md');

    snippets.forEach(snippet => {
      const rawSnippetString = getRawSnippetString(SNIPPETS_PATH, snippet);
      const snippetName = snippet.replace('.md', '');
      let code = getCode(rawSnippetString);
      if (nodeSnippets.includes(snippetName)) {
        requires.push(code.match(/const.*=.*require\(([^\)]*)\);/g));
        code = code.replace(/const.*=.*require\(([^\)]*)\);/g, '');
      }
      esmExportString += `export ${code}`;
      cjsExportString += code;
    });
    archivedSnippets.forEach(snippet => {
      const rawSnippetString = getRawSnippetString(
        SNIPPETS_ARCHIVE_PATH,
        snippet
      );
      cjsExportString += getCode(rawSnippetString);
    });

    requires = [
      ...new Set(
        requires
          .filter(Boolean)
          .map(v =>
            v[0].replace(
              'require(',
              'typeof require !== "undefined" && require('
            )
          )
      )
    ].join('\n');

    fs.writeFileSync(ROLLUP_INPUT_FILE, `${requires}\n\n${esmExportString}`);

    const testExports = `module.exports = {${[...snippets, ...archivedSnippets]
      .map(v => v.replace('.md', ''))
      .join(',')}}`;

    fs.writeFileSync(
      TEST_MODULE_FILE,
      `${requires}\n\n${cjsExportString}\n\n${testExports}`
    );

    // Check Travis builds - Will skip builds on Travis if not CRON/API
    if (util.isTravisCI() && util.isNotTravisCronOrAPI()) {
      fs.unlink(ROLLUP_INPUT_FILE);
      console.log(
        `${chalk.green(
          'NOBUILD'
        )} Module build terminated, not a cron job or a custom build!`
      );
      console.timeEnd('Packager');
      process.exit(0);
    }

    await doRollup();

    // Clean up the temporary input file Rollup used for building the module
    fs.unlink(ROLLUP_INPUT_FILE);

    console.log(`${chalk.green('SUCCESS!')} Snippet module built!`);
    console.timeEnd('Packager');
  } catch (err) {
    console.log(`${chalk.red('ERROR!')} During module creation: ${err}`);
    process.exit(1);
  }
}

// --- [94/100] unknown (electron/electron) ---

/**
 * Create a new guest instance.
 * @original_repo electron/electron
 * @original_name unknown
 */
function (embedder, params) {
  if (webViewManager == null) {
    webViewManager = process.electronBinding('web_view_manager')
  }

  const guest = webContents.create({
    isGuest: true,
    partition: params.partition,
    embedder: embedder
  })
  const guestInstanceId = guest.id
  guestInstances[guestInstanceId] = {
    guest: guest,
    embedder: embedder
  }

  // Clear the guest from map when it is destroyed.
  //
  // The guest WebContents is usually destroyed in 2 cases:
  // 1. The embedder frame is closed (reloaded or destroyed), and it
  //    automatically closes the guest frame.
  // 2. The guest frame is detached dynamically via JS, and it is manually
  //    destroyed when the renderer sends the GUEST_VIEW_MANAGER_DESTROY_GUEST
  //    message.
  // The second case relies on the libcc patch:
  //   https://github.com/electron/libchromiumcontent/pull/676
  // The patch was introduced to work around a bug in Chromium:
  //   https://github.com/electron/electron/issues/14211
  // We should revisit the bug to see if we can remove our libcc patch, the
  // patch was introduced in Chrome 66.
  guest.once('destroyed', () => {
    if (guestInstanceId in guestInstances) {
      detachGuest(embedder, guestInstanceId)
    }
  })

  // Init guest web view after attached.
  guest.once('did-attach', function (event) {
    params = this.attachParams
    delete this.attachParams

    const previouslyAttached = this.viewInstanceId != null
    this.viewInstanceId = params.instanceId

    // Only load URL and set size on first attach
    if (previouslyAttached) {
      return
    }

    if (params.src) {
      const opts = {}
      if (params.httpreferrer) {
        opts.httpReferrer = params.httpreferrer
      }
      if (params.useragent) {
        opts.userAgent = params.useragent
      }
      this.loadURL(params.src, opts)
    }
    guest.allowPopups = params.allowpopups
    embedder.emit('did-attach-webview', event, guest)
  })

  const sendToEmbedder = (channel, ...args) => {
    if (!embedder.isDestroyed()) {
      embedder._sendInternal(`${channel}-${guest.viewInstanceId}`, ...args)
    }
  }

  // Dispatch events to embedder.
  const fn = function (event) {
    guest.on(event, function (_, ...args) {
      sendToEmbedder('ELECTRON_GUEST_VIEW_INTERNAL_DISPATCH_EVENT', event, ...args)
    })
  }
  for (const event of supportedWebViewEvents) {
    fn(event)
  }

  // Dispatch guest's IPC messages to embedder.
  guest.on('ipc-message-host', function (_, channel, args) {
    sendToEmbedder('ELECTRON_GUEST_VIEW_INTERNAL_IPC_MESSAGE', channel, ...args)
  })

  // Notify guest of embedder window visibility when it is ready
  // FIXME Remove once https://github.com/electron/electron/issues/6828 is fixed
  guest.on('dom-ready', function () {
    const guestInstance = guestInstances[guestInstanceId]
    if (guestInstance != null && guestInstance.visibilityState != null) {
      guest._sendInternal('ELECTRON_GUEST_INSTANCE_VISIBILITY_CHANGE', guestInstance.visibilityState)
    }
  })

  // Forward internal web contents event to embedder to handle
  // native window.open setup
  guest.on('-add-new-contents', (...args) => {
    if (guest.getLastWebPreferences().nativeWindowOpen === true) {
      const embedder = getEmbedder(guestInstanceId)
      if (embedder != null) {
        embedder.emit('-add-new-contents', ...args)
      }
    }
  })

  return guestInstanceId
}

// --- [95/100] unknown (electron/electron) ---

/**
 * Attach the guest to an element of embedder.
 * @original_repo electron/electron
 * @original_name unknown
 */
function (event, embedderFrameId, elementInstanceId, guestInstanceId, params) {
  const embedder = event.sender
  // Destroy the old guest when attaching.
  const key = `${embedder.id}-${elementInstanceId}`
  const oldGuestInstanceId = embedderElementsMap[key]
  if (oldGuestInstanceId != null) {
    // Reattachment to the same guest is just a no-op.
    if (oldGuestInstanceId === guestInstanceId) {
      return
    }

    const oldGuestInstance = guestInstances[oldGuestInstanceId]
    if (oldGuestInstance) {
      oldGuestInstance.guest.detachFromOuterFrame()
    }
  }

  const guestInstance = guestInstances[guestInstanceId]
  // If this isn't a valid guest instance then do nothing.
  if (!guestInstance) {
    throw new Error(`Invalid guestInstanceId: ${guestInstanceId}`)
  }
  const { guest } = guestInstance
  if (guest.hostWebContents !== event.sender) {
    throw new Error(`Access denied to guestInstanceId: ${guestInstanceId}`)
  }

  // If this guest is already attached to an element then remove it
  if (guestInstance.elementInstanceId) {
    const oldKey = `${guestInstance.embedder.id}-${guestInstance.elementInstanceId}`
    delete embedderElementsMap[oldKey]

    // Remove guest from embedder if moving across web views
    if (guest.viewInstanceId !== params.instanceId) {
      webViewManager.removeGuest(guestInstance.embedder, guestInstanceId)
      guestInstance.embedder._sendInternal(`ELECTRON_GUEST_VIEW_INTERNAL_DESTROY_GUEST-${guest.viewInstanceId}`)
    }
  }

  const webPreferences = {
    guestInstanceId: guestInstanceId,
    nodeIntegration: params.nodeintegration != null ? params.nodeintegration : false,
    nodeIntegrationInSubFrames: params.nodeintegrationinsubframes != null ? params.nodeintegrationinsubframes : false,
    enableRemoteModule: params.enableremotemodule,
    plugins: params.plugins,
    zoomFactor: embedder.getZoomFactor(),
    webSecurity: !params.disablewebsecurity,
    enableBlinkFeatures: params.blinkfeatures,
    disableBlinkFeatures: params.disableblinkfeatures
  }

  // parse the 'webpreferences' attribute string, if set
  // this uses the same parsing rules as window.open uses for its features
  if (typeof params.webpreferences === 'string') {
    parseFeaturesString(params.webpreferences, function (key, value) {
      if (value === undefined) {
        // no value was specified, default it to true
        value = true
      }
      webPreferences[key] = value
    })
  }

  if (params.preload) {
    webPreferences.preloadURL = params.preload
  }

  // Return null from native window.open if allowpopups is unset
  if (webPreferences.nativeWindowOpen === true && !params.allowpopups) {
    webPreferences.disablePopups = true
  }

  // Security options that guest will always inherit from embedder
  const inheritedWebPreferences = new Map([
    ['contextIsolation', true],
    ['javascript', false],
    ['nativeWindowOpen', true],
    ['nodeIntegration', false],
    ['enableRemoteModule', false],
    ['sandbox', true],
    ['nodeIntegrationInSubFrames', false]
  ])

  // Inherit certain option values from embedder
  const lastWebPreferences = embedder.getLastWebPreferences()
  for (const [name, value] of inheritedWebPreferences) {
    if (lastWebPreferences[name] === value) {
      webPreferences[name] = value
    }
  }

  embedder.emit('will-attach-webview', event, webPreferences, params)
  if (event.defaultPrevented) {
    if (guest.viewInstanceId == null) guest.viewInstanceId = params.instanceId
    guest.destroy()
    return
  }

  guest.attachParams = params
  embedderElementsMap[key] = guestInstanceId

  guest.setEmbedder(embedder)
  guestInstance.embedder = embedder
  guestInstance.elementInstanceId = elementInstanceId

  watchEmbedder(embedder)

  webViewManager.addGuest(guestInstanceId, elementInstanceId, embedder, guest, webPreferences)
  guest.attachToIframe(embedder, embedderFrameId)
}

// --- [96/100] unknown (electron/electron) ---

/**
 * Remove an guest-embedder relationship.
 * @original_repo electron/electron
 * @original_name unknown
 */
function (embedder, guestInstanceId) {
  const guestInstance = guestInstances[guestInstanceId]
  if (embedder !== guestInstance.embedder) {
    return
  }

  webViewManager.removeGuest(embedder, guestInstanceId)
  delete guestInstances[guestInstanceId]

  const key = `${embedder.id}-${guestInstance.elementInstanceId}`
  delete embedderElementsMap[key]
}

// --- [97/100] unknown (electron/electron) ---

/**
 * Forward embedder window visiblity change events to guest
 * @original_repo electron/electron
 * @original_name unknown
 */
function (visibilityState) {
    for (const guestInstanceId in guestInstances) {
      const guestInstance = guestInstances[guestInstanceId]
      guestInstance.visibilityState = visibilityState
      if (guestInstance.embedder === embedder) {
        guestInstance.guest._sendInternal('ELECTRON_GUEST_INSTANCE_VISIBILITY_CHANGE', visibilityState)
      }
    }
  }

// --- [98/100] unknown (electron/electron) ---

/**
 * Returns WebContents from its guest id hosted in given webContents.
 * @original_repo electron/electron
 * @original_name unknown
 */
function (guestInstanceId, contents) {
  const guest = getGuest(guestInstanceId)
  if (!guest) {
    throw new Error(`Invalid guestInstanceId: ${guestInstanceId}`)
  }
  if (guest.hostWebContents !== contents) {
    throw new Error(`Access denied to guestInstanceId: ${guestInstanceId}`)
  }
  return guest
}

// --- [99/100] changesToRelease (electron/electron) ---

/**
 * function to determine if there have been commits to master since the last release
 * @original_repo electron/electron
 * @original_name changesToRelease
 */
async function changesToRelease () {
  const lastCommitWasRelease = new RegExp(`^Bump v[0-9.]*(-beta[0-9.]*)?(-nightly[0-9.]*)?$`, 'g')
  const lastCommit = await GitProcess.exec(['log', '-n', '1', `--pretty=format:'%s'`], gitDir)
  return !lastCommitWasRelease.test(lastCommit.stdout)
}

// --- [100/100] runRetryable (electron/electron) ---

/**
 * helper function to add some resiliency to volatile GH api endpoints
 * @original_repo electron/electron
 * @original_name runRetryable
 */
async function runRetryable (fn, maxRetries) {
  let lastError
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      await new Promise((resolve, reject) => setTimeout(resolve, CHECK_INTERVAL))
      lastError = error
    }
  }
  // Silently eat 404s.
  if (lastError.status !== 404) throw lastError
}

// === END OF FILE ===
