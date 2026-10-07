// Command go-removal creates a compilable zero-behavior mutant of one function.
// Types, signatures, imports and the original body remain type-checked. The
// runtime returns zero values before reaching the original body; a compilation
// failure or panic is never evidence that a behavioral assertion caught it.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
	"io"
	"os"
	"strings"
)

type function struct {
	Index       int    `json:"index"`
	Name        string `json:"name"`
	Line        int    `json:"line"`
	EndLine     int    `json:"end_line"`
	Constructor bool   `json:"constructor"`
}

func main() {
	index := flag.Int("index", -1, "function index; absent lists candidates")
	flag.Parse()
	if err := transform(os.Stdin, os.Stdout, *index); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func transform(input io.Reader, output io.Writer, index int) error {
	source, err := io.ReadAll(io.LimitReader(input, 4<<20))
	if err != nil {
		return err
	}
	set := token.NewFileSet()
	file, err := parser.ParseFile(set, "implementation.go", source, parser.ParseComments)
	if err != nil {
		return err
	}
	var candidates []function
	var functions []*ast.FuncDecl
	for _, decl := range file.Decls {
		fn, ok := decl.(*ast.FuncDecl)
		if !ok || fn.Body == nil || fn.Name.Name == "init" || fn.Name.Name == "main" {
			continue
		}
		name := fn.Name.Name
		if fn.Recv != nil {
			name = "method." + name
		}
		candidates = append(candidates, function{Index: len(functions), Name: name,
			Line: set.Position(fn.Pos()).Line, EndLine: set.Position(fn.End()).Line,
			Constructor: strings.HasPrefix(fn.Name.Name, "New")})
		functions = append(functions, fn)
	}
	if index < 0 {
		return json.NewEncoder(output).Encode(candidates)
	}
	if index >= len(functions) {
		return fmt.Errorf("function index out of range")
	}
	fn := functions[index]
	var statements []ast.Stmt
	var results []ast.Expr
	if fn.Type.Results != nil {
		for _, field := range fn.Type.Results.List {
			count := len(field.Names)
			if count == 0 {
				count = 1
			}
			for i := 0; i < count; i++ {
				name := ast.NewIdent(fmt.Sprintf("_phpretroRemovalResult%d", len(results)))
				statements = append(statements, &ast.DeclStmt{Decl: &ast.GenDecl{Tok: token.VAR,
					Specs: []ast.Spec{&ast.ValueSpec{Names: []*ast.Ident{name}, Type: field.Type}}}})
				results = append(results, ast.NewIdent(name.Name))
			}
		}
	}
	statements = append(statements, &ast.ReturnStmt{Results: results})
	fn.Body.List = append([]ast.Stmt{&ast.IfStmt{Cond: ast.NewIdent("true"), Body: &ast.BlockStmt{List: statements}}}, fn.Body.List...)
	return format.Node(output, set, file)
}
