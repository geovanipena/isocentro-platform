# lib — DLLs de referência da Varian (fora do git)

Esta pasta guarda as DLLs do ESAPI necessárias para **compilar/typecheck** os scripts
localmente. Elas são **proprietárias da Varian** e ficam **fora do git**
(veja `.gitignore`: `lib/*.dll`). Cada máquina precisa copiá-las uma vez.

## O que copiar

Do servidor Eclipse (GAC de 64 bits):

```
C:\Windows\Microsoft.NET\assembly\GAC_64\   ->   lib\
    VMS.TPS.Common.Model.API.dll
    VMS.TPS.Common.Model.Types.dll
```

> A versão de referência do projeto é a **15.6.8.73** (AssemblyVersion 1.0.300.11),
> a mesma dos XMLs em `vendor/esapi-docs/`. Use as DLLs do mesmo Eclipse do deploy.

## Para que serve

Com as duas DLLs aqui, o typecheck compila cada script single-file em
**C# 5 / .NET Framework 4.5.2 / warnings-as-error**, espelhando o compilador
single-file do Eclipse e pegando erros ANTES do deploy:

```
powershell -ExecutionPolicy Bypass -File tools\typecheck.ps1
```

Sem as DLLs, o typecheck sai com código 3 e é apenas **pulado** (os demais checks
continuam rodando).
